--
-- PostgreSQL database dump
--

\restrict 8ZHQ0fnIoYhsigEeNXB0blTlh22Nj9fIG7U2CDPrHjgpggqnlgqezvU1PrrACD6

-- Dumped from database version 17.6 (Debian 17.6-1.pgdg12+1)
-- Dumped by pg_dump version 17.7 (Debian 17.7-0+deb13u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: documents; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.documents (id, title, body, category, version, created_at, published_date, is_deprecated, deprecation_note, tags, embedding, trap_set, trap_type) FROM stdin;
\.


--
-- PostgreSQL database dump complete
--

\unrestrict 8ZHQ0fnIoYhsigEeNXB0blTlh22Nj9fIG7U2CDPrHjgpggqnlgqezvU1PrrACD6

