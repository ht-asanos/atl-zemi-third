"""データ投入・定期更新 CLI

使用方法:
    uv run python -m app.services.data_loader init
    uv run python -m app.services.data_loader backfill
    uv run python -m app.services.data_loader refresh-recipes
"""

import asyncio
import sys

from app.services.cli.mext_commands import cmd_init, cmd_load_mext_excel, cmd_update_display_names
from app.services.cli.recipe_commands import (
    cmd_backfill,
    cmd_fetch_recipes_by_keyword,
    cmd_normalize_ingredient_backfill,
    cmd_prune_non_meal_recipes,
    cmd_rebuild_recipe_ingredients,
    cmd_refresh_recipes,
    cmd_repair_youtube_nutrition,
    cmd_run_recipe_maintenance,
)
from app.services.cli.youtube_commands import (
    cmd_check_youtube_transcript,
    cmd_fetch_youtube_recipes,
    cmd_ingest_training_progressions,
)


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python -m app.services.data_loader "
            "<init|backfill|refresh-recipes|fetch-recipes-by-keyword|fetch-youtube-recipes|check-youtube-transcript|"
            "repair-youtube-nutrition|rebuild-recipe-ingredients|update-display-names|prune-non-meal-recipes|"
            "ingest-training-progressions|"
            "normalize-ingredient-backfill|load-mext-excel|run-recipe-maintenance>"
        )
        sys.exit(1)

    command = sys.argv[1]
    commands = {
        "init": cmd_init,
        "backfill": cmd_backfill,
        "refresh-recipes": cmd_refresh_recipes,
        "fetch-recipes-by-keyword": cmd_fetch_recipes_by_keyword,
        "fetch-youtube-recipes": cmd_fetch_youtube_recipes,
        "check-youtube-transcript": cmd_check_youtube_transcript,
        "ingest-training-progressions": cmd_ingest_training_progressions,
        "repair-youtube-nutrition": cmd_repair_youtube_nutrition,
        "rebuild-recipe-ingredients": cmd_rebuild_recipe_ingredients,
        "update-display-names": cmd_update_display_names,
        "prune-non-meal-recipes": cmd_prune_non_meal_recipes,
        "normalize-ingredient-backfill": cmd_normalize_ingredient_backfill,
        "load-mext-excel": cmd_load_mext_excel,
        "run-recipe-maintenance": cmd_run_recipe_maintenance,
    }

    if command not in commands:
        print(f"Unknown command: {command}")
        print(f"Available: {', '.join(commands)}")
        sys.exit(1)

    # prune-non-meal-recipes は --execute フラグをサポート
    if command == "prune-non-meal-recipes":
        execute = "--execute" in sys.argv[2:]
        asyncio.run(commands[command](execute=execute))
    elif command == "run-recipe-maintenance":
        triggered_by = "manual"
        for idx, arg in enumerate(sys.argv[2:], start=2):
            if arg == "--triggered-by" and idx + 1 < len(sys.argv):
                triggered_by = sys.argv[idx + 1]
                break
        asyncio.run(commands[command](triggered_by=triggered_by))
    else:
        asyncio.run(commands[command]())


if __name__ == "__main__":
    main()
