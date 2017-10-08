CREATE USER "user" WITH PASSWORD 'user';
CREATE DATABASE "exercise" WITH OWNER="user" ENCODING='UTF8' TEMPLATE=template0;
\connect "exercise";
CREATE EXTENSION postgis;
CREATE SCHEMA exercise;
GRANT ALL PRIVILEGES ON SCHEMA exercise TO "user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA exercise TO "user";
CREATE TABLE exercise.bookmarks (
	id  serial  primary key,
	lat real,
	lon real,
	label varchar(15),
	size smallint CHECK (size >= 1 AND size <= 5),  
	geom geometry(POINT,4326)
	);	
GRANT ALL PRIVILEGES ON TABLE exercise.bookmarks TO "user";
CREATE INDEX idx_bookmarks_geom ON exercise.bookmarks USING GIST(geom);
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA exercise TO "user";