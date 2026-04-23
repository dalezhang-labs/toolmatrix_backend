-- Migration: Convert image-count quota to credit-based quota
-- Free tier: 100 credits/month, each image costs 20 credits (= 5 images)

-- 1. Rename usage_logs column: images_translated → credits_used
--    Multiply existing values by 20 to convert image count to credits
ALTER TABLE imagelingo.usage_logs
  ADD COLUMN IF NOT EXISTS credits_used INT DEFAULT 0;

UPDATE imagelingo.usage_logs
  SET credits_used = COALESCE(images_translated, 0) * 20
  WHERE credits_used = 0 AND images_translated > 0;

-- 2. Rename subscriptions column: images_limit → credits_limit
--    Convert existing limits: 5 images → 100 credits
ALTER TABLE imagelingo.subscriptions
  ADD COLUMN IF NOT EXISTS credits_limit INT DEFAULT 100;

UPDATE imagelingo.subscriptions
  SET credits_limit = COALESCE(images_limit, 5) * 20
  WHERE credits_limit = 100 AND images_limit IS NOT NULL AND images_limit != 5;

-- Note: old columns (images_translated, images_limit) are kept for safety.
-- Drop them after verifying the migration works:
-- ALTER TABLE imagelingo.usage_logs DROP COLUMN IF EXISTS images_translated;
-- ALTER TABLE imagelingo.subscriptions DROP COLUMN IF EXISTS images_limit;
