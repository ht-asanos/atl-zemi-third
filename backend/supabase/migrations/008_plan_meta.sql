-- plan_meta: プラン生成時の mode / staple_name を保存する
alter table daily_plans add column plan_meta jsonb;

-- upsert_weekly_plans を plan_meta 対応版に更新
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
        insert into daily_plans (user_id, plan_date, meal_plan, workout_plan, plan_meta)
        values (
            (plan_item->>'user_id')::uuid,
            (plan_item->>'plan_date')::date,
            (plan_item->'meal_plan')::jsonb,
            (plan_item->'workout_plan')::jsonb,
            (plan_item->'plan_meta')::jsonb
        )
        on conflict (user_id, plan_date)
        do update set
            meal_plan = excluded.meal_plan,
            workout_plan = excluded.workout_plan,
            plan_meta = excluded.plan_meta,
            updated_at = now();
    end loop;
end;
$$;
