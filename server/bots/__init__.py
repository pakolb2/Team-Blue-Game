"""
server/bots/__init__.py
------------------------
Bot package.

Available bots:
    RandomBot      — plays a random legal card each turn      (Phase 6)
    RuleBasedBot   — applies standard Jass heuristics         (Phase 6)

Usage:
    from server.bots.random_bot import RandomBot
    from server.bots.rule_based_bot import RuleBasedBot

    bot = RuleBasedBot(player_id="bot_seat_2")
"""
