-- Cases base model, simplified.
-- In: description — one or two sentences on what the case is.
-- Out: waiting_on (status 'waiting' + next_action says it) and category (free
-- text with no behaviour; an instance that wants it adds it back as its own
-- field, config/models.json). A value a row already holds is not lost: it
-- moves into extra under the same key, or under <key>_old when extra already
-- has that key.

ALTER TABLE cases_case ADD COLUMN description TEXT;

UPDATE cases_case SET extra = json_set(extra,
    CASE WHEN json_type(extra, '$.waiting_on') IS NULL THEN '$.waiting_on' ELSE '$.waiting_on_old' END, waiting_on)
  WHERE waiting_on IS NOT NULL;
UPDATE cases_case SET extra = json_set(extra,
    CASE WHEN json_type(extra, '$.category') IS NULL THEN '$.category' ELSE '$.category_old' END, category)
  WHERE category IS NOT NULL;

ALTER TABLE cases_case DROP COLUMN waiting_on;
ALTER TABLE cases_case DROP COLUMN category;
