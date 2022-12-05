# game_service: hypercorn game_service --reload --debug --bind api.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG
user_service: hypercorn user_service --reload --debug --bind user_service.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG

leaderboard_service: hypercorn leaderboard_service --reload --debug --bind leaderboard_service.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG


game_service1: hypercorn game_service --reload --debug --bind game_service.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG
game_service2: hypercorn game_service --reload --debug --bind game_service.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG
game_service3: hypercorn game_service --reload --debug --bind game_service.local.gd:$PORT --access-logfile - --error-logfile - --log-level DEBUG

primary: ./bin/litefs -config ./config/primary.yml
secondary: ./bin/litefs -config ./config/secondary.yml
secondary1: ./bin/litefs -config ./config/secondary1.yml