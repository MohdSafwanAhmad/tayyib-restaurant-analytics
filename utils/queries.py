# utils/queries.py
from .db import get_df

def get_restaurant_id_for_login(restaurant_name: str):
    q = """
    SELECT id
    FROM public.restaurants
    WHERE name ILIKE %s
    LIMIT 1;
    """
    return get_df(q, (restaurant_name,))

def get_claims_for_restaurant(restaurant_id: int):
    # alias columns so pages never have to rename
    q = """
    SELECT
        csr.claimed_at AS created_at,
        csr.profile_id,
        r.name AS restaurant_name
    FROM public.claimed_stamp_rewards csr
    JOIN public.restaurants r ON csr.restaurant_id = r.id
    WHERE csr.restaurant_id = %s
    ORDER BY csr.claimed_at;
    """
    return get_df(q, (restaurant_id,))

def get_claims_with_desc(restaurant_id: int):
    q = """
    SELECT
        csr.id,
        csr.profile_id,
        csr.restaurant_id,
        csr.claimed_at AS created_at,
        csr.restaurant_stamp_reward_id,
        rsr.description
    FROM public.claimed_stamp_rewards csr
    JOIN public.restaurant_stamp_rewards rsr
      ON csr.restaurant_stamp_reward_id = rsr.id
    WHERE csr.restaurant_id = %s
    ORDER BY csr.claimed_at;
    """
    return get_df(q, (restaurant_id,))

def get_profile_stamp_analytics(restaurant_id: int):
    q = """
    SELECT profile_id, created_at
    FROM public.profile_stamp_analytics
    WHERE restaurant_id = %s
    ORDER BY created_at;
    """
    return get_df(q, (restaurant_id,))

# Example: “performance flex” query with window fn you can mention in interview
def get_daily_active_users(restaurant_id: int):
    q = """
    WITH activity AS (
      SELECT profile_id, created_at::date AS day
      FROM public.profile_stamp_analytics
      WHERE restaurant_id = %s
      UNION ALL
      SELECT profile_id, claimed_at::date AS day
      FROM public.claimed_stamp_rewards
      WHERE restaurant_id = %s
    )
    SELECT day, COUNT(DISTINCT profile_id) AS unique_users
    FROM activity
    GROUP BY day
    ORDER BY day;
    """
    return get_df(q, (restaurant_id, restaurant_id))

# Add these functions to your existing utils/queries.py file

def get_existing_offers(restaurant_id: int):
    """Get all active offers for a restaurant with redemption counts"""
    q = """
    SELECT 
        o.id,
        o.about,
        o.offer_type,
        o.valid_days_of_week,
        o.valid_start_time,
        o.valid_end_time,
        o.start_date,
        o.end_date,
        o.unique_usage_per_user,
        o.created_at,
        ot.en as offer_type_name,
        COALESCE(COUNT(or_red.id), 0) as redemption_count,
        -- Surprise bag details if applicable
        sb.price,
        sb.estimated_value,
        sb.daily_quantity,
        sb.current_daily_quantity,
        sb.total_quantity
    FROM public.offers o
    JOIN public.offer_types ot ON o.offer_type = ot.id
    LEFT JOIN public.offer_redemptions or_red ON o.id = or_red.offer_id
    LEFT JOIN public.surprise_bags sb ON o.id = sb.offer_id
    WHERE o.restaurant_id = %s
    GROUP BY o.id, o.about, o.offer_type, o.valid_days_of_week, o.valid_start_time, 
             o.valid_end_time, o.start_date, o.end_date, o.unique_usage_per_user, 
             o.created_at, ot.en, sb.price, sb.estimated_value, sb.daily_quantity, 
             sb.current_daily_quantity, sb.total_quantity
    ORDER BY o.created_at DESC;
    """
    return get_df(q, (restaurant_id,))

def get_offer_redemption_count(offer_id: str):
    """Get redemption count for a specific offer"""
    q = """
    SELECT COUNT(*) as count
    FROM public.offer_redemptions
    WHERE offer_id = %s;
    """
    result = get_df(q, (offer_id,))
    return result.iloc[0]['count'] if not result.empty else 0

def get_offer_types():
    """Get all available offer types"""
    q = """
    SELECT id, en, fr
    FROM public.offer_types
    ORDER BY id;
    """
    return get_df(q, ())

def check_offer_exists_in_db(restaurant_id: int, offer_title: str, offer_type: str):
    """Check if an offer with the same title and type exists in the database"""
    q = """
    SELECT COUNT(*) as count
    FROM public.offers o
    JOIN public.offer_types ot ON o.offer_type = ot.id
    WHERE o.restaurant_id = %s 
    AND o.about->'en'->>'title' = %s
    AND ot.en = %s;
    """
    result = get_df(q, (restaurant_id, offer_title, offer_type))
    return result.iloc[0]['count'] > 0 if not result.empty else False