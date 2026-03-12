"""トレーニングテンプレート定義 (diet / strength / bouldering)

種目 ID は英語スネークケース固定キー。name_ja は日本語表示名。
"""

from app.models.training import Exercise, MuscleGroup, TrainingDay, TrainingTemplate

G = MuscleGroup


def get_diet_template() -> TrainingTemplate:
    """diet: 全身大筋群、中強度。"""
    return TrainingTemplate(
        goal="diet",
        days=[
            TrainingDay(
                day_label="全身A",
                exercises=[
                    Exercise(
                        id="goblet_squat",
                        name_ja="ゴブレットスクワット",
                        muscle_group=G.LEGS,
                        sets=3,
                        reps=15,
                    ),
                    Exercise(
                        id="push_up",
                        name_ja="プッシュアップ",
                        muscle_group=G.CHEST,
                        sets=3,
                        reps=12,
                    ),
                    Exercise(
                        id="bodyweight_row",
                        name_ja="自重ロウ",
                        muscle_group=G.BACK,
                        sets=3,
                        reps=12,
                    ),
                    Exercise(
                        id="plank",
                        name_ja="プランク",
                        muscle_group=G.CORE,
                        sets=3,
                        reps="30秒",
                    ),
                ],
            ),
            TrainingDay(
                day_label="全身B",
                exercises=[
                    Exercise(
                        id="lunge",
                        name_ja="ランジ",
                        muscle_group=G.LEGS,
                        sets=3,
                        reps=12,
                    ),
                    Exercise(
                        id="dumbbell_press",
                        name_ja="ダンベルプレス",
                        muscle_group=G.CHEST,
                        sets=3,
                        reps=12,
                    ),
                    Exercise(
                        id="dumbbell_row",
                        name_ja="ダンベルロウ",
                        muscle_group=G.BACK,
                        sets=3,
                        reps=12,
                    ),
                    Exercise(
                        id="dead_bug",
                        name_ja="デッドバグ",
                        muscle_group=G.CORE,
                        sets=3,
                        reps=10,
                    ),
                ],
            ),
        ],
    )


def get_strength_template() -> TrainingTemplate:
    """strength: Push/Pull/Legs 分割、漸進性過負荷。"""
    return TrainingTemplate(
        goal="strength",
        days=[
            TrainingDay(
                day_label="Push",
                exercises=[
                    Exercise(
                        id="bench_press",
                        name_ja="ベンチプレス",
                        muscle_group=G.CHEST,
                        sets=4,
                        reps=8,
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="overhead_press",
                        name_ja="オーバーヘッドプレス",
                        muscle_group=G.SHOULDERS,
                        sets=3,
                        reps=10,
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="tricep_dip",
                        name_ja="ディップス",
                        muscle_group=G.ARMS,
                        sets=3,
                        reps=10,
                    ),
                ],
            ),
            TrainingDay(
                day_label="Pull",
                exercises=[
                    Exercise(
                        id="pull_up",
                        name_ja="チンニング",
                        muscle_group=G.BACK,
                        sets=4,
                        reps=8,
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="barbell_row",
                        name_ja="バーベルロウ",
                        muscle_group=G.BACK,
                        sets=3,
                        reps=10,
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="barbell_curl",
                        name_ja="バーベルカール",
                        muscle_group=G.ARMS,
                        sets=3,
                        reps=12,
                    ),
                ],
            ),
            TrainingDay(
                day_label="Legs",
                exercises=[
                    Exercise(
                        id="barbell_squat",
                        name_ja="バーベルスクワット",
                        muscle_group=G.LEGS,
                        sets=4,
                        reps=8,
                        rest_seconds=120,
                    ),
                    Exercise(
                        id="romanian_deadlift",
                        name_ja="ルーマニアンデッドリフト",
                        muscle_group=G.LEGS,
                        sets=3,
                        reps=10,
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="calf_raise",
                        name_ja="カーフレイズ",
                        muscle_group=G.LEGS,
                        sets=3,
                        reps=15,
                    ),
                ],
            ),
        ],
    )


def get_bouldering_template() -> TrainingTemplate:
    """bouldering: 週4日（2登る + 2補強）向けの基本日テンプレート。"""
    return TrainingTemplate(
        goal="bouldering",
        days=[
            TrainingDay(
                day_label="Climb A (Technique + Endurance)",
                exercises=[
                    Exercise(
                        id="scapular_pull_up",
                        name_ja="スキャプラプルアップ",
                        muscle_group=G.BACK,
                        sets=3,
                        reps=10,
                        rest_seconds=75,
                    ),
                    Exercise(
                        id="bodyweight_row",
                        name_ja="自重ロウ",
                        muscle_group=G.BACK,
                        sets=3,
                        reps=12,
                        rest_seconds=75,
                    ),
                    Exercise(
                        id="dead_hang",
                        name_ja="デッドハング",
                        muscle_group=G.FOREARMS,
                        sets=2,
                        reps="20秒",
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="hollow_body_hold",
                        name_ja="ホロウボディホールド",
                        muscle_group=G.CORE,
                        sets=3,
                        reps="30秒",
                        rest_seconds=60,
                    ),
                ],
            ),
            TrainingDay(
                day_label="Support A (Pull + Core)",
                exercises=[
                    Exercise(
                        id="pull_up",
                        name_ja="チンニング",
                        muscle_group=G.BACK,
                        sets=3,
                        reps=6,
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="dumbbell_row",
                        name_ja="ダンベルロウ",
                        muscle_group=G.BACK,
                        sets=3,
                        reps=10,
                        rest_seconds=75,
                    ),
                    Exercise(
                        id="hanging_knee_raise",
                        name_ja="ハンギングニーレイズ",
                        muscle_group=G.CORE,
                        sets=3,
                        reps=12,
                        rest_seconds=60,
                    ),
                    Exercise(
                        id="pallof_press",
                        name_ja="パロフプレス",
                        muscle_group=G.CORE,
                        sets=3,
                        reps=10,
                        rest_seconds=60,
                    ),
                ],
            ),
            TrainingDay(
                day_label="Climb B (Power + Movement)",
                exercises=[
                    Exercise(
                        id="pull_up",
                        name_ja="チンニング",
                        muscle_group=G.BACK,
                        sets=4,
                        reps=6,
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="farmer_carry",
                        name_ja="ファーマーズキャリー",
                        muscle_group=G.FOREARMS,
                        sets=2,
                        reps="30秒",
                        rest_seconds=90,
                    ),
                    Exercise(
                        id="hanging_leg_raise",
                        name_ja="ハンギングレッグレイズ",
                        muscle_group=G.CORE,
                        sets=3,
                        reps=10,
                        rest_seconds=60,
                    ),
                ],
            ),
            TrainingDay(
                day_label="Support B (Core + Lower + Push)",
                exercises=[
                    Exercise(
                        id="goblet_squat",
                        name_ja="ゴブレットスクワット",
                        muscle_group=G.LEGS,
                        sets=3,
                        reps=10,
                        rest_seconds=75,
                    ),
                    Exercise(
                        id="push_up",
                        name_ja="プッシュアップ",
                        muscle_group=G.CHEST,
                        sets=3,
                        reps=12,
                        rest_seconds=60,
                    ),
                    Exercise(
                        id="side_plank",
                        name_ja="サイドプランク",
                        muscle_group=G.CORE,
                        sets=3,
                        reps="30秒",
                        rest_seconds=45,
                    ),
                ],
            ),
        ],
    )


def get_template(goal: str) -> TrainingTemplate:
    """目的に応じたテンプレートを返す。"""
    templates = {
        "diet": get_diet_template,
        "strength": get_strength_template,
        "bouldering": get_bouldering_template,
    }
    factory = templates.get(goal)
    if factory is None:
        raise ValueError(f"Unknown goal: {goal}")
    return factory()
