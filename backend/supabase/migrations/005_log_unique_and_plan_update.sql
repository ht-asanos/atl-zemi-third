-- Step 0-1: ログ重複防止ユニーク制約

-- 同日・同食事タイプは1件のみ (upsert で上書き)
ALTER TABLE meal_logs
  ADD CONSTRAINT uq_meal_logs_user_date_type UNIQUE (user_id, log_date, meal_type);

-- 同日・同種目は1件のみ (upsert で上書き)
ALTER TABLE workout_logs
  ADD CONSTRAINT uq_workout_logs_user_date_exercise UNIQUE (user_id, log_date, exercise_id);

-- Step 0-2: daily_plans 更新用 RPC (楽観ロック付き)

CREATE OR REPLACE FUNCTION update_daily_plan(
  p_plan_id uuid,
  p_meal_plan jsonb,
  p_workout_plan jsonb,
  p_expected_updated_at timestamptz
) RETURNS void AS $$
BEGIN
  UPDATE daily_plans
  SET meal_plan = p_meal_plan,
      workout_plan = p_workout_plan,
      updated_at = now()
  WHERE id = p_plan_id
    AND updated_at = p_expected_updated_at;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Conflict: plan was modified by another operation'
      USING ERRCODE = '40001';
  END IF;
END;
$$ LANGUAGE plpgsql;
