-- seed.sql
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

use codenovadb;

START TRANSACTION;

/* 1) User: 고정 PK (u001~u010)*/
-- (수정된) 1) User: password 컬럼 추가
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

/* 1) User */
INSERT INTO user (
  "id","email","name","phone","gender","birthday","rank","department","status",
  "is_active","is_staff","is_superuser","password","last_login","created_at","updated_at"
) VALUES
('u001','u001@example.com','홍길동','010-1111-1111','male','1990-01-01','사원','콘텐츠','approved',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u002','u002@example.com','이영희','010-1111-1112','female','1992-02-02','대리','영업지원','pending',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u003','u003@example.com','박철수','010-1111-1113','male','1988-03-03','과장','고객지원','approved',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u004','u004@example.com','최지현','010-1111-1114','female','1995-04-04','차장','콘텐츠','rejected',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u005','u005@example.com','김민수','010-1111-1115','male','1985-05-05','부장','영업지원','approved',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u006','u006@example.com','정수진','010-1111-1116','female','1991-06-06','사원','고객지원','pending',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u007','u007@example.com','한지훈','010-1111-1117','male','1993-07-07','대리','콘텐츠','approved',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u008','u008@example.com','오은정','010-1111-1118','female','1996-08-08','과장','영업지원','pending',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u009','u009@example.com','서준호','010-1111-1119','male','1989-09-09','차장','고객지원','approved',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP),
('u010','u010@example.com','배수지','010-1111-1120','female','1994-10-10','부장','콘텐츠','approved',1,0,0,'',NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP);

/* 2) ApprovalLog — rejected만 reason */
INSERT INTO "approval_log" ("user_id","action","reason","created_at") VALUES
('u001','approved',NULL,CURRENT_TIMESTAMP),
('u002','pending',NULL,CURRENT_TIMESTAMP),
('u003','approved',NULL,CURRENT_TIMESTAMP),
('u004','rejected','서류 미비',CURRENT_TIMESTAMP),
('u005','approved',NULL,CURRENT_TIMESTAMP),
('u006','pending',NULL,CURRENT_TIMESTAMP),
('u007','approved',NULL,CURRENT_TIMESTAMP),
('u008','pending',NULL,CURRENT_TIMESTAMP),
('u009','rejected','승인 거부 사유: 자격 미달',CURRENT_TIMESTAMP),
('u010','approved',NULL,CURRENT_TIMESTAMP);

/* 3) ApiKey — (user, name) 유니크 */
INSERT INTO "api_key" ("user_id","name","secret_key","created_at") VALUES
('u001','key-u001','sk_abc123u001',CURRENT_TIMESTAMP),
('u002','key-u002','sk_abc123u002',CURRENT_TIMESTAMP),
('u003','key-u003','sk_abc123u003',CURRENT_TIMESTAMP),
('u004','key-u004','sk_abc123u004',CURRENT_TIMESTAMP),
('u005','key-u005','sk_abc123u005',CURRENT_TIMESTAMP),
('u006','key-u006','sk_abc123u006',CURRENT_TIMESTAMP),
('u007','key-u007','sk_abc123u007',CURRENT_TIMESTAMP),
('u008','key-u008','sk_abc123u008',CURRENT_TIMESTAMP),
('u009','key-u009','sk_abc123u009',CURRENT_TIMESTAMP),
('u010','key-u010','sk_abc123u010',CURRENT_TIMESTAMP);

/* 4) ChatSession — 제목을 고유값으로 */
INSERT INTO "chat_session" ("user_id","title","mode","created_at") VALUES
('u001','SEED_SES_01 검색 테스트','google_api',CURRENT_TIMESTAMP),
('u002','SEED_SES_02 내부 QA','internal',CURRENT_TIMESTAMP),
('u003','SEED_SES_03 상품 문의','google_api',CURRENT_TIMESTAMP),
('u004','SEED_SES_04 컨텐츠 아이디어','internal',CURRENT_TIMESTAMP),
('u005','SEED_SES_05 고객지원 대화','internal',CURRENT_TIMESTAMP),
('u006','SEED_SES_06 테스트 케이스','google_api',CURRENT_TIMESTAMP),
('u007','SEED_SES_07 개발 회의','internal',CURRENT_TIMESTAMP),
('u008','SEED_SES_08 업무 보고','google_api',CURRENT_TIMESTAMP),
('u009','SEED_SES_09 고객 피드백','internal',CURRENT_TIMESTAMP),
('u010','SEED_SES_10 사내 공지','google_api',CURRENT_TIMESTAMP);

/* 5) ChatMessage — 세션은 제목으로 안전 참조 */
INSERT INTO "chat_message" ("session_id","role","content","created_at") VALUES
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_01 검색 테스트'),'user','SEED_MSG_01 안녕하세요?',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_01 검색 테스트'),'assistant','SEED_MSG_02 무엇을 도와드릴까요?',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_02 내부 QA'),'user','SEED_MSG_03 QA 항목 정리해 주세요.',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_02 내부 QA'),'assistant','SEED_MSG_04 목록을 알려드릴게요.',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_03 상품 문의'),'user','SEED_MSG_05 상품 재고 있나요?',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_03 상품 문의'),'assistant','SEED_MSG_06 네, 20개 있습니다.',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_04 컨텐츠 아이디어'),'user','SEED_MSG_07 기획안 작성 중이에요.',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_04 컨텐츠 아이디어'),'assistant','SEED_MSG_08 참고 자료 드릴게요.',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_05 고객지원 대화'),'user','SEED_MSG_09 고객 불만이 접수되었습니다.',CURRENT_TIMESTAMP),
((SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_05 고객지원 대화'),'assistant','SEED_MSG_10 CS팀에 전달했습니다.',CURRENT_TIMESTAMP);

/* 6) Card — 일부는 세션 NULL */
INSERT INTO "card" ("user_id","session_id","title","created_at") VALUES
('u001',(SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_01 검색 테스트'),'SEED_CARD_01 FAQ 정리',CURRENT_TIMESTAMP),
('u002',(SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_02 내부 QA'),'SEED_CARD_02 QA 노트',CURRENT_TIMESTAMP),
('u003',(SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_03 상품 문의'),'SEED_CARD_03 상품 문의 카드',CURRENT_TIMESTAMP),
('u004',(SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_04 컨텐츠 아이디어'),'SEED_CARD_04 아이디어 카드',CURRENT_TIMESTAMP),
('u005',(SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_05 고객지원 대화'),'SEED_CARD_05 고객지원 카드',CURRENT_TIMESTAMP),
('u006',NULL,'SEED_CARD_06 개인 메모',CURRENT_TIMESTAMP),
('u007',(SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_07 개발 회의'),'SEED_CARD_07 회의 카드',CURRENT_TIMESTAMP),
('u008',(SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_08 업무 보고'),'SEED_CARD_08 보고 카드',CURRENT_TIMESTAMP),
('u009',NULL,'SEED_CARD_09 잡다한 메모',CURRENT_TIMESTAMP),
('u010',(SELECT "id" FROM "chat_session" WHERE "title"='SEED_SES_10 사내 공지'),'SEED_CARD_10 공지 카드',CURRENT_TIMESTAMP);

/* 7) CardMessage — (card, message) 유니크 */
INSERT INTO "card_message" ("card_id","message_id","position") VALUES
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_01 FAQ 정리'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_01 안녕하세요?'), 1),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_01 FAQ 정리'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_02 무엇을 도와드릴까요?'), 2),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_02 QA 노트'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_03 QA 항목 정리해 주세요.'), 1),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_02 QA 노트'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_04 목록을 알려드릴게요.'), 2),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_03 상품 문의 카드'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_05 상품 재고 있나요?'), 1),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_03 상품 문의 카드'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_06 네, 20개 있습니다.'), 2),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_04 아이디어 카드'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_07 기획안 작성 중이에요.'), 1),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_04 아이디어 카드'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_08 참고 자료 드릴게요.'), 2),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_05 고객지원 카드'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_09 고객 불만이 접수되었습니다.'), 1),
((SELECT "id" FROM "card" WHERE "title"='SEED_CARD_05 고객지원 카드'), (SELECT "id" FROM "chat_message" WHERE "content"='SEED_MSG_10 CS팀에 전달했습니다.'), 2);

COMMIT;

COMMIT;
