-- SQLite

-- 1. 删除用户
DELETE FROM users WHERE username='111';

-- 2. 修改用户ID
-- 删除这个用户的所有会话
DELETE FROM sessions WHERE user_id = 旧ID;
-- 修改用户ID
UPDATE users SET id = 新ID WHERE id = 旧ID;