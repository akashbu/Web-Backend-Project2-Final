from quart import Quart, request, make_response
from quart_schema import QuartSchema, validate_request 

import dataclasses
import redis
import utils.helpers as helpers

app = Quart(__name__)
QuartSchema(app)



@dataclasses.dataclass
class GameResult:
    gameid: str
    username: str
    numguesses: int
    gameresult: int # 1 for win and 0 for loss



@app.route("/leaderboard/add", methods=["POST"])
@validate_request(GameResult)
async def addGamesResult(data):
    app.logger.info(data)
    # instatiate Redis
    r = redis.Redis(host='127.0.0.1', port=6379)

    # converts the GameResult object into a dictionary
    data = dataclasses.asdict(data)

    r.hset(data["gameid"], "username", data["username"])
    r.hset(data["gameid"], "numguesses", data["numguesses"])
    r.hset(data["gameid"], "gameresult", data["gameresult"])

    r.hincrby(data["username"], "gamecount", 1)   # increment user's gamecount
    
    userCurrentScore = r.hget(data["username"], "score")
    userTotGames = r.hget(data["username"], "gamecount")

    newScore = computeScore(data["numguesses"], data["gameresult"])

    if(userTotGames is None):
        userTotGames = 1
    if (userCurrentScore is None):
        userCurrentScore = 0

    userCurrentScore = userCurrentScore.decode("utf-8")
    userTotGames = userTotGames.decode("utf-8")

    newScore = (int(newScore)) + (int(float(userCurrentScore)))
    newScore = int(newScore) // int(userTotGames)

    r.hset(data["username"], "score", newScore)

    r.zadd("players", newScore, data["username"])

    return {
        "new score" : newScore
    }

@app.route("/", methods=["GET"])
async def home():
    """
    Home
    
    This is just the welcome message.
    """
    
    return helpers.jsonify_message("Welcome to leaderboard service.")

@app.route("/leaderboard/topten", methods=(["GET"]))
async def getTopTen():
    r = redis.Redis(host='127.0.0.1', port=6379)
    arr = r.zrange("players", 0, -1, desc=True)
    result = {}
    i = 0
    rlen = len(result)
    while (i < 10 and rlen > 0):
        result[i] = arr[i]
        i += 1
        rlen -= 1

    return result 


def computeScore(numGuessses, gamesResult):
    if (gamesResult == 0): return 0
    
    if (numGuessses == 1): return 6
    elif (numGuessses == 2): return 5
    elif (numGuessses == 3): return 4
    elif (numGuessses == 4): return 3
    elif (numGuessses == 5): return 2
    elif (numGuessses == 6): return 1
    else: return 0


# ---------------------------------------------------------------------------- #
#                                error handlers                                #
# ---------------------------------------------------------------------------- #
@app.errorhandler(400)
async def bad_request(e):
    return {"error": f"Bad Request: {e.description}"}, 400


@app.errorhandler(401)
async def unauthorized(e):
    response = await make_response({"error": f"Unauthorized: {e.description}"}, 401)
    response.status_code = 401
    response.headers["WWW-Authenticate"] = 'Basic realm="User Login"'
    return response


@app.errorhandler(404)
async def not_found(e):
    return {"error": f"Not Found: {e.description}"}, 404


@app.errorhandler(409)
async def username_exists(e):
    return {"error": "Username already exists"}, 409



