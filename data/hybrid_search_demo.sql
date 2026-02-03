--
-- PostgreSQL database dump
--

\restrict CWSYHgCozsDeGf9IrQgpnVA6QuaI7ZmaCdO4UmEvPPZKErb5cc6oy0cIwgvPGtS

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

SET default_table_access_method = "heap";

--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE "public"."documents" (
    "id" "text" NOT NULL,
    "title" "text" NOT NULL,
    "body" "text" NOT NULL,
    "category" "text",
    "version" "text",
    "created_at" timestamp with time zone NOT NULL,
    "published_date" timestamp with time zone,
    "is_deprecated" boolean DEFAULT false,
    "deprecation_note" "text",
    "tags" "text"[],
    "search_vector" "tsvector" GENERATED ALWAYS AS (("setweight"("to_tsvector"('"english"'::"regconfig", COALESCE("title", ''::"text")), 'A'::"char") || "setweight"("to_tsvector"('"english"'::"regconfig", COALESCE("body", ''::"text")), 'B'::"char"))) STORED,
    "embedding" "public"."vector"(768),
    "trap_set" "text",
    "trap_type" "text"
);


--
-- Data for Name: documents; Type: TABLE DATA; Schema: public; Owner: -
--

COPY "public"."documents" ("id", "title", "body", "category", "version", "created_at", "published_date", "is_deprecated", "deprecation_note", "tags", "embedding", "trap_set", "trap_type") FROM stdin;
\.


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "documents_pkey" PRIMARY KEY ("id", "created_at");


--
-- Name: documents_created_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "documents_created_at_idx" ON "public"."documents" USING "btree" ("created_at" DESC);


--
-- Name: documents_embedding_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "documents_embedding_idx" ON "public"."documents" USING "diskann" ("embedding");


--
-- Name: documents_search_vector_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "documents_search_vector_idx" ON "public"."documents" USING "gin" ("search_vector");


--
-- PostgreSQL database dump complete
--

\unrestrict CWSYHgCozsDeGf9IrQgpnVA6QuaI7ZmaCdO4UmEvPPZKErb5cc6oy0cIwgvPGtS

