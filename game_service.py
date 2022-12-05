# Project 2 - API Gateway - Wordle Mock Backend

import toml
import sqlite3
import databases
import base64
import dataclasses
import uuid

import utils.helpers as helpers

from typing import Tuple, Optional
from quart import Quart, jsonify, g, request, abort
from quart_schema import QuartSchema, validate_request
from itertools import cycle

app = Quart(__name__)
QuartSchema(app)

app.config.from_file(f"./config/app.toml", toml.load)


@dataclasses.dataclass
class Guess:
    guess: str


@dataclasses.dataclass
class Username:
    username: str

iter = cycle(["GAME1", "GAME2", "GAME3"])

async def _connect_db(dbVal):

    database = databases.Database(app.config["DATABASES"][dbVal])
    await database.connect()
    return database


def _get_db(dbVal):
    if not hasattr(g, "sqlite_db"):
        g.sqlite_db = _connect_db(dbVal)
    return g.sqlite_db


@app.teardown_appcontext
async def close_connection(exception):
    db = getattr(g, "_sqlite_db", None)
    if db is not None:
        await db.disconnect()


# ----------------------------Routes---------------------------- #

@app.route("/", methods=["GET"])
async def home():
    """
    Home
    
    This is just the welcome message.
    """
    
    return helpers.jsonify_message("Welcome to game service.")

@app.route("/wordle/start", methods=["POST"])
async def start_game():
    """
    Start Game
    
    Initializes a game. Returns the game ID if successful.
    """
    username = request.authorization.username

    dbVal = next(iter)
    db =  await _get_db(dbVal)

    query = "SELECT word FROM secret_word ORDER BY RANDOM() LIMIT 1"
    app.logger.info(query), app.logger.warning(query)
    secret_word = await db.fetch_one(query=query)

    try:
        gameid = str(uuid.uuid4())
        query = "INSERT INTO games(gameid, username, secretWord) VALUES(:gameid, :username, :secret_word)"
        values = {"gameid":gameid, "username": username, "secret_word": secret_word.word}
        
        db = await _get_db("GAME1")
        await db.execute(query=query, values=values)
    except sqlite3.IntegrityError as e:
        abort(409, e)
    return helpers.jsonify_message(f"Game started with id: {gameid}.")


@app.route("/wordle/games", methods=["GET"])
async def list_active_games():
    """
    List Active Games
    
    This generates a list of game IDs that are active. Games that ran out of attempts 
    or games that have been won are not included in the list.
    """
    username = request.authorization.username

    dbVal = next(iter)

    db =  await _get_db(dbVal)
    query = """
            SELECT gameid FROM games WHERE username = :username AND isActive = 1
            """
    app.logger.info(query), app.logger.warning(query)
    games = await db.fetch_all(query=query, values={"username": username})

    if games:
        return list(map(dict, games))
    else:
        return helpers.jsonify_message(f"No active games found for user, {username}."), 404


async def game_is_active(db, username, gameid) -> bool:
    query = """
            SELECT * FROM games WHERE username = :username AND gameid = :gameid AND isActive = 1
            """
    app.logger.info(query), app.logger.warning(query)
    game = await db.fetch_one(query=query, values={"username": username, "gameid": gameid})
    if game:
        return True
    else:
        return False
        

@app.route("/wordle/<string:gameid>/status", methods=["GET"])
async def retrieve_game(gameid):
    """
    Retrieve Game
    
    This displays the current state of a specified active game. It lists all the attempts, as well as,
    the details of how close the attempts are from the secret word. This also shows the number
    of attempts left before the game ends.
    """
    username = request.authorization.username

    dbVal = next(iter)
    db =  await _get_db(dbVal)

    if await game_is_active(db, username, gameid):
        query = """
                SELECT guess, secretWord as secret_word
                FROM guesses
                LEFT JOIN games ON guesses.gameid = games.gameid
                WHERE games.gameid = :gameid AND isActive = 1
                """
        app.logger.info(query), app.logger.warning(query)
        guesses = await db.fetch_all(query=query, values={"gameid": gameid})

        return calculate_game_status(guesses)
    else:
        abort(404)


def calculate_game_status(guesses):
    # Clean up and check guesses:
    num_guesses = len(guesses)
    list_guesses = []
    for guess in guesses:
        correct_letters, correct_indices = helpers.compare_guess(guess.guess, guess.secret_word)
        list_guesses.append({
            "guess": guess.guess,
            "correct_letters": correct_letters,
            "correct_indices": correct_indices
        })

    return {
        "num_guesses": num_guesses,
        "max_attempts": app.config["WORDLE"]["MAX_NUM_ATTEMPTS"],
        "guesses": list_guesses
    }


@app.route("/wordle/<string:gameid>/guess", methods=["POST"])
@validate_request(Guess)
async def make_guess(gameid, data: Guess):
    """
    Guess the Secret Word
    
    This inserts a guess into the guesses table if the guess word is a valid word. If the
    guess is valid, it will show whether it is correct and display hints accordingly. It
    will also tell the player how many attempts they have left.
    """
    username = request.authorization.username
    data = await request.get_json()

    dbVal = next(iter)

    db =  await _get_db(dbVal)

    if await game_is_active(db, username, gameid):
        # Validate the guessed word first:
        if len(data["guess"]) != app.config["WORDLE"]["WORDLE_LENGTH"]:
            return helpers.jsonify_message(f"Not a valid guess! Please only guess {app.config['WORDLE']['WORDLE_LENGTH']}-letter words. This attempt does not count.")
        else:
            query = "SELECT * FROM valid_words WHERE word = :guess"
            app.logger.info(query), app.logger.warning(query)
            is_valid = await db.fetch_one(query=query, values={"guess": data["guess"]})

            if not is_valid:
                return helpers.jsonify_message(f"{data['guess']} is not a valid word! Try again. This attempt does not count.")

        # guess was valid, proceed to store and check game state
        try:
            query = """
                    INSERT INTO guesses(gameid, guess) VALUES(:gameid, :guess)
                    """

            db = _get_db("GAME1")
            await db.execute(query=query, values={"gameid": gameid, "guess": data["guess"]})
        except sqlite3.IntegrityError as e:
            # guesses are unique per game
            abort(409, e)
        
        # grab the secret word
        query = """
                SELECT secretWord AS secret_word FROM games WHERE gameid = :gameid
                """
        app.logger.info(query), app.logger.warning(query)

        dbVal = next(iter)
        db = _get_db("GAME1")

        game = await db.fetch_one(query=query, values={"gameid": gameid})
        secret_word = game.secret_word 


        query = """
                SELECT guess, secretWord as secret_word
                FROM guesses
                LEFT JOIN games ON guesses.gameid = games.gameid
                WHERE games.gameid = :gameid AND isActive = 1
                """
        app.logger.info(query), app.logger.warning(query)
        guesses = await db.fetch_all(query=query, values={"gameid": gameid})
        guesses = calculate_game_status(guesses)

        is_correct = helpers.check_guess(data["guess"], secret_word)
        max_num_attempts = app.config["WORDLE"]["MAX_NUM_ATTEMPTS"]

        if is_correct:
            query = """
                    UPDATE games 
                    SET isActive = 0, hasWon = 1
                    WHERE gameid = :gameid
                    """
            db = _get_db("GAME1")
            await db.execute(query=query, values={"gameid": gameid})

            return helpers.jsonify_message(f"Correct! The answer was {secret_word}.")
        elif guesses["num_guesses"] == max_num_attempts and not is_correct:
            query = """
                    UPDATE games 
                    SET isActive = 0
                    WHERE gameid = :gameid
                    """
            
            db = await _get_db("GAME1")
            await db.execute(query=query, values={"gameid": gameid})
            
            return helpers.jsonify_message(f"You have lost! You have made {max_num_attempts} incorrect attempts. The secret word was {secret_word}.")
        else:
            remaining_attempts = max_num_attempts - guesses["num_guesses"]
            return {
                "message": f"Try again! You have {remaining_attempts} more attampts left.",
                "guesses": guesses
            }
    else:
        abort(404)


@app.errorhandler(404)
def not_found(e):
    return {"error": "The resource could not be found"}, 404


@app.errorhandler(409)
def conflict(e):
    return {"error": str(e)}, 409