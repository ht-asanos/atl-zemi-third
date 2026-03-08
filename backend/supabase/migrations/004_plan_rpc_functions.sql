-- Phase 2a: RPC 関数 (security invoker)

-- goals テーブルに unique 制約を追加 (upsert 用)
create unique index if not exists idx_goals_user_goal_type on goals(user_id, goal_type);

-- upsert_weekly_plans: 7日分を1トランザクションで upsert
create or replace function upsert_weekly_plans(p_plans jsonb)
returns void
language plpgsql
security invoker
set search_path = public
as $$
declare
    plan_item jsonb;
begin
    for plan_item in select * from jsonb_array_elements(p_plans)
    loop
        insert into daily_plans (user_id, plan_date, meal_plan, workout_plan)
        values (
            (plan_item->>'user_id')::uuid,
            (plan_item->>'plan_date')::date,
            (plan_item->'meal_plan')::jsonb,
            (plan_item->'workout_plan')::jsonb
        )
        on conflict (user_id, plan_date)
        do update set
            meal_plan = excluded.meal_plan,
            workout_plan = excluded.workout_plan,
            updated_at = now();
    end loop;
end;
$$;

-- update_meal_plan: 食事プラン部分更新
create or replace function update_meal_plan(p_plan_id uuid, p_new_meal_plan jsonb)
returns void
language plpgsql
security invoker
set search_path = public
as $$
begin
    update daily_plans
    set meal_plan = p_new_meal_plan,
        updated_at = now()
    where id = p_plan_id;

    if not found then
        raise exception 'Plan not found: %', p_plan_id;
    end if;
end;
$$;
