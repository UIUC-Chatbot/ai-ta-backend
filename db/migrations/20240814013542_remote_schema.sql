
SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

CREATE EXTENSION IF NOT EXISTS "pg_tle";

-- CREATE EXTENSION IF NOT EXISTS "supabase-dbdev" WITH SCHEMA "public";

CREATE EXTENSION IF NOT EXISTS "pgsodium" WITH SCHEMA "pgsodium";

CREATE EXTENSION IF NOT EXISTS "http" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "hypopg" WITH SCHEMA "public";

-- CREATE EXTENSION IF NOT EXISTS "olirice-index_advisor" WITH SCHEMA "public";

CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";

CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";

CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";

CREATE OR REPLACE FUNCTION "public"."add_document_to_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) RETURNS boolean
    LANGUAGE "plpgsql"
    AS $$DECLARE
    v_document_id bigint;
    v_doc_group_id bigint;
    v_success boolean := true;
    p_doc_group text;
BEGIN
    -- Ensure the document exists
    SELECT id INTO v_document_id FROM public.documents WHERE course_name = p_course_name AND (
    (s3_path <> '' AND s3_path IS NOT NULL AND s3_path = p_s3_path) OR
    (url = p_url)
);

    raise log 'id of document: %', v_document_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Document does not exist';
    END IF;

    -- Loop through document groups
    FOREACH p_doc_group IN ARRAY p_doc_groups
    LOOP
        -- Upsert document group, assuming 'name' and 'course_name' can uniquely identify a row
        INSERT INTO public.doc_groups(name, course_name)
        VALUES (p_doc_group, p_course_name)
        ON CONFLICT (name, course_name) DO UPDATE
        SET name = EXCLUDED.name
        RETURNING id INTO v_doc_group_id;

        raise log 'id of document group: %', v_doc_group_id;

        -- Upsert the association in documents_doc_groups
        INSERT INTO public.documents_doc_groups(document_id, doc_group_id)
        VALUES (v_document_id, v_doc_group_id)
        ON CONFLICT (document_id, doc_group_id) DO NOTHING;

        raise log 'completed for %',v_doc_group_id;
    END LOOP;

    raise log 'completed for %',v_document_id;
    RETURN v_success;
EXCEPTION
    WHEN OTHERS THEN
        v_success := false;
        RAISE;
        RETURN v_success;
END;$$;

ALTER FUNCTION "public"."add_document_to_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."add_document_to_group_url"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) RETURNS boolean
    LANGUAGE "plpgsql"
    AS $$DECLARE
    v_document_id bigint;
    v_doc_group_id bigint;
    v_success boolean := true;
    p_doc_group text;
BEGIN
    -- Ensure the document exists
    SELECT id INTO v_document_id FROM public.documents WHERE course_name = p_course_name AND (
    (s3_path <> '' AND s3_path IS NOT NULL AND s3_path = p_s3_path)
);

    raise log 'id of document: %', v_document_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Document does not exist';
    END IF;

    -- Loop through document groups
    FOREACH p_doc_group IN ARRAY p_doc_groups
    LOOP
        -- Upsert document group, assuming 'name' and 'course_name' can uniquely identify a row
        INSERT INTO public.doc_groups(name, course_name)
        VALUES (p_doc_group, p_course_name)
        ON CONFLICT (name, course_name) DO UPDATE
        SET name = EXCLUDED.name
        RETURNING id INTO v_doc_group_id;

        raise log 'id of document group: %', v_doc_group_id;

        -- Upsert the association in documents_doc_groups
        INSERT INTO public.documents_doc_groups(document_id, doc_group_id)
        VALUES (v_document_id, v_doc_group_id)
        ON CONFLICT (document_id, doc_group_id) DO NOTHING;

        raise log 'completed for %',v_doc_group_id;
    END LOOP;

    raise log 'completed for %',v_document_id;
    RETURN v_success;
EXCEPTION
    WHEN OTHERS THEN
        v_success := false;
        RAISE;
        RETURN v_success;
END;$$;

ALTER FUNCTION "public"."add_document_to_group_url"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."c"() RETURNS "record"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    course_names record;
BEGIN
    SELECT distinct course_name INTO course_names
    FROM public.documents
    LIMIT 1;

    RAISE LOG 'distinct_course_names: %', course_names;
    RETURN course_names;
END;$$;

ALTER FUNCTION "public"."c"() OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."check_and_lock_flows_v2"("id" integer) RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    workflow_id bigint;
    workflow_locked boolean;
BEGIN
    -- Get the latest workflow id and its lock status
    select latest_workflow_id, is_locked
    into workflow_id, workflow_locked
    from public.n8n_workflows
    order by latest_workflow_id desc
    limit 1;

    -- Check if the latest workflow is locked
    if id = workflow_id then
        return 'id already exists';
    elseif workflow_locked then
        return 'Workflow is locked';
    else
        -- Update the latest_workflow_id
        update public.n8n_workflows
        set latest_workflow_id = id,
        is_locked = True
        where latest_workflow_id = workflow_id;
        return 'Workflow updated';

    
    end if;
end;$$;

ALTER FUNCTION "public"."check_and_lock_flows_v2"("id" integer) OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."cn"() RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    course_names text;
BEGIN
    SELECT distinct course_name INTO course_names
    FROM public.documents;

    RAISE LOG 'distinct_course_names: %', course_names;
    RETURN course_names;
END;$$;

ALTER FUNCTION "public"."cn"() OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."get_course_names"() RETURNS "json"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    course_names text;
BEGIN
    -- Get the latest workflow id and its lock status
    SELECT distinct course_name INTO course_names
    FROM public.documents;

    RAISE LOG 'distinct_course_names: %', course_names;
    RETURN course_names;
END;$$;

ALTER FUNCTION "public"."get_course_names"() OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."get_distinct_course_names"() RETURNS TABLE("course_name" "text")
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT d.course_name
    FROM public.documents d
    WHERE d.course_name IS NOT NULL;

    RAISE LOG 'Distinct course names retrieved';
END;
$$;

ALTER FUNCTION "public"."get_distinct_course_names"() OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."get_latest_workflow_id"() RETURNS bigint
    LANGUAGE "plpgsql"
    AS $$DECLARE
    v_workflow_id bigint;
BEGIN
    -- Get the latest workflow id and its lock status
    SELECT latest_workflow_id INTO v_workflow_id
    FROM public.n8n_workflows
    ORDER BY latest_workflow_id DESC
    LIMIT 1;

    RAISE LOG 'latest_workflow_id: %', v_workflow_id;
    RETURN v_workflow_id;
END;$$;

ALTER FUNCTION "public"."get_latest_workflow_id"() OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."hello"() RETURNS "text"
    LANGUAGE "sql"
    AS $$select 'hello world';$$;

ALTER FUNCTION "public"."hello"() OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."increment"("usage" integer, "apikey" "text") RETURNS "void"
    LANGUAGE "sql"
    AS $$
					update api_keys 
					set usage_count = usage_count + usage
					where key = apikey
				$$;

ALTER FUNCTION "public"."increment"("usage" integer, "apikey" "text") OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."increment_api_usage"("usage" integer, "apikey" "text") RETURNS "void"
    LANGUAGE "sql" SECURITY DEFINER
    AS $_$create function increment (usage int, apikey string)
				returns void as
				$$
					update api_keys 
					set usage_count = usage_count + usage
					where api_key = apiKey
				$$ 
				language sql volatile;$_$;

ALTER FUNCTION "public"."increment_api_usage"("usage" integer, "apikey" "text") OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."increment_api_usage_count"("usage" integer, "apikey" "text") RETURNS "void"
    LANGUAGE "sql" SECURITY DEFINER
    AS $_$create function increment (usage int, apikey text)
				returns void as
				$$
					update api_keys 
					set usage_count = usage_count + usage
					where key = apikey
				$$ 
				language sql volatile;$_$;

ALTER FUNCTION "public"."increment_api_usage_count"("usage" integer, "apikey" "text") OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."increment_workflows"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$BEGIN
    -- Increase doc_count on insert
    IF TG_OP = 'INSERT' THEN
        UPDATE n8n_workflows
        SET latest_workflow_id = NEW.latest_workflow_id,
        is_locked = True
        WHERE latest_workflow_id = NEW.latest_workflow_id;
        RETURN NEW;
    -- Decrease doc_count on delete
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE n8n_workflows
        SET latest_workflow_id = OLD.latest_workflow_id,
        is_locked = False
        WHERE latest_workflow_id = OLD.latest_workflow_id;
        RETURN OLD;
    END IF;
    RETURN NULL; -- Should never reach here
END;$$;

ALTER FUNCTION "public"."increment_workflows"() OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."remove_document_from_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_doc_group" "text") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    v_document_id bigint;
    v_doc_group_id bigint;
    v_doc_count bigint;
BEGIN
    -- Check if the document exists
    SELECT id INTO v_document_id FROM public.documents WHERE course_name = p_course_name AND (
    (s3_path <> '' AND s3_path IS NOT NULL AND s3_path = p_s3_path) OR
    (url = p_url)
);
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Document does not exist';
    END IF;

    -- Check if the document group exists
    SELECT id, doc_count INTO v_doc_group_id, v_doc_count
    FROM public.doc_groups
    WHERE name = p_doc_group AND course_name = p_course_name;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Document group does not exist';
    END IF;

    -- Delete the association
    DELETE FROM public.documents_doc_groups
    WHERE document_id = v_document_id AND doc_group_id = v_doc_group_id;

    -- If the doc_count becomes 0, delete the doc_group
    IF v_doc_count = 1 THEN
        DELETE FROM public.doc_groups
        WHERE id = v_doc_group_id;
    END IF;
END;$$;

ALTER FUNCTION "public"."remove_document_from_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_doc_group" "text") OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."update_doc_count"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$BEGIN
    -- Increase doc_count on insert
    IF TG_OP = 'INSERT' THEN
        UPDATE doc_groups
        SET doc_count = doc_count + 1
        WHERE id = NEW.doc_group_id;
        RETURN NEW;
    -- Decrease doc_count on delete
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE doc_groups
        SET doc_count = doc_count - 1
        WHERE id = OLD.doc_group_id;
        RETURN OLD;
    END IF;
    RETURN NULL; -- Should never reach here
END;$$;

ALTER FUNCTION "public"."update_doc_count"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";

CREATE TABLE IF NOT EXISTS "public"."api_keys" (
    "user_id" "text" NOT NULL,
    "key" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "modified_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "usage_count" bigint DEFAULT '0'::bigint NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL
);

ALTER TABLE "public"."api_keys" OWNER TO "postgres";

COMMENT ON COLUMN "public"."api_keys"."user_id" IS 'User ID from Clerk auth';

CREATE TABLE IF NOT EXISTS "public"."course_names" (
    "course_name" "text"
);

ALTER TABLE "public"."course_names" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."depricated_uiuc_chatbot" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "metadata" "json",
    "content" "text"
);

ALTER TABLE "public"."depricated_uiuc_chatbot" OWNER TO "postgres";

COMMENT ON TABLE "public"."depricated_uiuc_chatbot" IS 'Depricated course materials';

CREATE TABLE IF NOT EXISTS "public"."documents" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "s3_path" "text",
    "readable_filename" "text",
    "course_name" "text",
    "url" "text",
    "contexts" "jsonb",
    "base_url" "text"
);

ALTER TABLE "public"."documents" OWNER TO "postgres";

COMMENT ON TABLE "public"."documents" IS 'Course materials, full info for each document';

COMMENT ON COLUMN "public"."documents"."base_url" IS 'Input url for web scraping function';

CREATE OR REPLACE VIEW "public"."distinct_course_names" AS
 SELECT DISTINCT "documents"."course_name"
   FROM "public"."documents";

ALTER TABLE "public"."distinct_course_names" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."doc_groups" (
    "id" bigint NOT NULL,
    "name" "text" NOT NULL,
    "course_name" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "enabled" boolean DEFAULT true NOT NULL,
    "private" boolean DEFAULT true NOT NULL,
    "doc_count" bigint DEFAULT '0'::bigint
);

ALTER TABLE "public"."doc_groups" OWNER TO "postgres";

COMMENT ON TABLE "public"."doc_groups" IS 'This table is to store metadata for the document groups';

ALTER TABLE "public"."doc_groups" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."doc_groups_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."documents_doc_groups" (
    "document_id" bigint NOT NULL,
    "doc_group_id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);

ALTER TABLE "public"."documents_doc_groups" OWNER TO "postgres";

COMMENT ON TABLE "public"."documents_doc_groups" IS 'This is a junction table between documents and doc_groups';

ALTER TABLE "public"."documents_doc_groups" ALTER COLUMN "document_id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."documents_doc_groups_document_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."documents_failed" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "s3_path" "text",
    "readable_filename" "text",
    "course_name" "text",
    "url" "text",
    "contexts" "jsonb",
    "base_url" "text",
    "doc_groups" "text",
    "error" "text"
);

ALTER TABLE "public"."documents_failed" OWNER TO "postgres";

COMMENT ON TABLE "public"."documents_failed" IS 'Documents that failed to ingest. If we retry and they succeed, it should be removed from this table.';

ALTER TABLE "public"."documents_failed" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."documents_failed_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

ALTER TABLE "public"."documents" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."documents_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."documents_in_progress" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "s3_path" "text",
    "readable_filename" "text",
    "course_name" "text",
    "url" "text",
    "contexts" "jsonb",
    "base_url" "text",
    "doc_groups" "text",
    "error" "text",
    "beam_task_id" "text"
);

ALTER TABLE "public"."documents_in_progress" OWNER TO "postgres";

COMMENT ON TABLE "public"."documents_in_progress" IS 'Document ingest in progress. In Beam.cloud ingest queue.';

ALTER TABLE "public"."documents_in_progress" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."documents_in_progress_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."documents_v2" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "course_name" "text",
    "readable_filename" "text",
    "s3_path" "text",
    "url" "text",
    "base_url" "text",
    "contexts" "jsonb"
);

ALTER TABLE "public"."documents_v2" OWNER TO "postgres";

ALTER TABLE "public"."documents_v2" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."documents_v2_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."email-newsletter" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "email" "text",
    "unsubscribed-from-newsletter" boolean
);

ALTER TABLE "public"."email-newsletter" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."insights" (
    "insight_id" bigint NOT NULL,
    "document_id" bigint,
    "name" "text" NOT NULL,
    "insight" "jsonb",
    "description" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);

ALTER TABLE "public"."insights" OWNER TO "postgres";

ALTER TABLE "public"."insights" ALTER COLUMN "insight_id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."insights_insight_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."llm-convo-monitor" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "convo" "json",
    "convo_id" "text",
    "course_name" "text",
    "user_email" "text"
);

ALTER TABLE "public"."llm-convo-monitor" OWNER TO "postgres";

COMMENT ON COLUMN "public"."llm-convo-monitor"."convo_id" IS 'id from Conversation object in Typescript.';

COMMENT ON COLUMN "public"."llm-convo-monitor"."user_email" IS 'The users'' email address (first email only, if they have multiple)';

ALTER TABLE "public"."llm-convo-monitor" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."llm-convo-monitor_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."n8n_workflows" (
    "latest_workflow_id" bigint NOT NULL,
    "is_locked" boolean NOT NULL
);

ALTER TABLE "public"."n8n_workflows" OWNER TO "postgres";

COMMENT ON TABLE "public"."n8n_workflows" IS 'Just the highest number of the latest workflow being run...';

COMMENT ON COLUMN "public"."n8n_workflows"."latest_workflow_id" IS 'The highest possible workflow number as it corresponds to N8n workflow IDs.';

COMMENT ON COLUMN "public"."n8n_workflows"."is_locked" IS 'During the time between when we getExpectedWorkflowID and the time that we actually start the workflow, another workflow could be started.';

ALTER TABLE "public"."n8n_workflows" ALTER COLUMN "latest_workflow_id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."n8n_api_keys_in_progress_workflow_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."nal_publications" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "doi" "text",
    "title" "text",
    "publisher" "text",
    "license" "text",
    "doi_number" "text",
    "metadata" "jsonb",
    "link" "text"
);

ALTER TABLE "public"."nal_publications" OWNER TO "postgres";

ALTER TABLE "public"."nal_publications" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."nal_publications_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."projects" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "course_name" character varying,
    "doc_map_id" character varying,
    "convo_map_id" character varying,
    "n8n_api_key" "text",
    "last_uploaded_doc_id" bigint,
    "last_uploaded_convo_id" bigint,
    "subscribed" bigint,
    "description" "text",
    "insight_schema" "json"
);

ALTER TABLE "public"."projects" OWNER TO "postgres";

COMMENT ON COLUMN "public"."projects"."n8n_api_key" IS 'N8N API key(s) for each course. If multiple users create tools, they EACH need to store their API key.';

ALTER TABLE "public"."projects" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."projects_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."publications" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "pmid" character varying NOT NULL,
    "pmcid" character varying,
    "doi" character varying,
    "journal_title" character varying,
    "article_title" character varying,
    "issn" character varying,
    "published" "date",
    "last_revised" "date",
    "license" character varying,
    "modified_at" timestamp with time zone DEFAULT "now"(),
    "full_text" boolean,
    "live" boolean,
    "release_date" "date",
    "pubmed_ftp_link" "text",
    "filepath" "text",
    "xml_filename" "text"
);

ALTER TABLE "public"."publications" OWNER TO "postgres";

COMMENT ON COLUMN "public"."publications"."filepath" IS 'A comma-separated list of filepaths. Either to the .txt for abstracts, or to PDFs for full text. There can be multiple PDFs (supplementary materials, etc) per article.';

ALTER TABLE "public"."publications" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."publications_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

ALTER TABLE "public"."depricated_uiuc_chatbot" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."uiuc-chatbot_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."uiuc-course-table" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "total_tokens" real,
    "total_prompt_price" real,
    "total_completions_price" real,
    "total_embeddings_price" real,
    "total_queries" real,
    "course_name" "text"
);

ALTER TABLE "public"."uiuc-course-table" OWNER TO "postgres";

COMMENT ON TABLE "public"."uiuc-course-table" IS 'Details about each course';

ALTER TABLE "public"."uiuc-course-table" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."uiuc-course-table_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE IF NOT EXISTS "public"."usage_metrics" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "course_name" "text",
    "total_docs" bigint,
    "total_convos" bigint,
    "most_recent_convo" timestamp without time zone,
    "owner_name" "text",
    "admin_name" "text"
);

ALTER TABLE "public"."usage_metrics" OWNER TO "postgres";

ALTER TABLE "public"."usage_metrics" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."usage_metrics_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

ALTER TABLE ONLY "public"."api_keys"
    ADD CONSTRAINT "api_keys_pkey" PRIMARY KEY ("user_id");

ALTER TABLE ONLY "public"."doc_groups"
    ADD CONSTRAINT "doc_groups_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."documents_doc_groups"
    ADD CONSTRAINT "documents_doc_groups_pkey" PRIMARY KEY ("document_id", "doc_group_id");

ALTER TABLE ONLY "public"."documents_failed"
    ADD CONSTRAINT "documents_failed_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."documents_in_progress"
    ADD CONSTRAINT "documents_in_progress_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "documents_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."documents_v2"
    ADD CONSTRAINT "documents_v2_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."email-newsletter"
    ADD CONSTRAINT "email-newsletter_email_key" UNIQUE ("email");

ALTER TABLE ONLY "public"."email-newsletter"
    ADD CONSTRAINT "email-newsletter_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."insights"
    ADD CONSTRAINT "insights_pkey" PRIMARY KEY ("insight_id");

ALTER TABLE ONLY "public"."llm-convo-monitor"
    ADD CONSTRAINT "llm-convo-monitor_convo_id_key" UNIQUE ("convo_id");

ALTER TABLE ONLY "public"."llm-convo-monitor"
    ADD CONSTRAINT "llm-convo-monitor_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."n8n_workflows"
    ADD CONSTRAINT "n8n_api_keys_pkey" PRIMARY KEY ("latest_workflow_id");

ALTER TABLE ONLY "public"."nal_publications"
    ADD CONSTRAINT "nal_publications_doi_key" UNIQUE ("doi");

ALTER TABLE ONLY "public"."nal_publications"
    ADD CONSTRAINT "nal_publications_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_course_name_key" UNIQUE ("course_name");

ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."publications"
    ADD CONSTRAINT "publications_id_key" UNIQUE ("id");

ALTER TABLE ONLY "public"."publications"
    ADD CONSTRAINT "publications_pkey" PRIMARY KEY ("pmid");

ALTER TABLE ONLY "public"."publications"
    ADD CONSTRAINT "publications_pmid_key" UNIQUE ("pmid");

ALTER TABLE ONLY "public"."depricated_uiuc_chatbot"
    ADD CONSTRAINT "uiuc-chatbot_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."uiuc-course-table"
    ADD CONSTRAINT "uiuc-course-table_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."doc_groups"
    ADD CONSTRAINT "unique_name_course_name" UNIQUE ("name", "course_name");

ALTER TABLE ONLY "public"."usage_metrics"
    ADD CONSTRAINT "usage_metrics_pkey" PRIMARY KEY ("id");

CREATE INDEX "doc_groups_enabled_course_name_idx" ON "public"."doc_groups" USING "btree" ("enabled", "course_name");

CREATE INDEX "documents_course_name_idx" ON "public"."documents" USING "hash" ("course_name");

CREATE INDEX "documents_created_at_idx" ON "public"."documents" USING "btree" ("created_at");

CREATE INDEX "documents_doc_groups_doc_group_id_idx" ON "public"."documents_doc_groups" USING "btree" ("doc_group_id");

CREATE INDEX "documents_doc_groups_document_id_idx" ON "public"."documents_doc_groups" USING "btree" ("document_id");

CREATE INDEX "idx_doc_s3_path" ON "public"."documents" USING "btree" ("s3_path");

CREATE INDEX "insights_document_id_idx" ON "public"."insights" USING "btree" ("document_id");

CREATE INDEX "insights_insight_gin_idx" ON "public"."insights" USING "gin" ("insight");

CREATE INDEX "insights_name_idx" ON "public"."insights" USING "btree" ("name");

CREATE INDEX "llm-convo-monitor_convo_id_idx" ON "public"."llm-convo-monitor" USING "hash" ("convo_id");

CREATE INDEX "llm-convo-monitor_course_name_idx" ON "public"."llm-convo-monitor" USING "hash" ("course_name");

CREATE OR REPLACE TRIGGER "trg_update_doc_count_after_insert" AFTER INSERT OR DELETE ON "public"."documents_doc_groups" FOR EACH ROW EXECUTE FUNCTION "public"."update_doc_count"();

ALTER TABLE ONLY "public"."insights"
    ADD CONSTRAINT "insights_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."documents"("id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_subscribed_fkey" FOREIGN KEY ("subscribed") REFERENCES "public"."doc_groups"("id") ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY "public"."documents_doc_groups"
    ADD CONSTRAINT "public_documents_doc_groups_doc_group_id_fkey" FOREIGN KEY ("doc_group_id") REFERENCES "public"."doc_groups"("id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."documents_doc_groups"
    ADD CONSTRAINT "public_documents_doc_groups_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."documents"("id") ON DELETE CASCADE;

CREATE POLICY "Enable execute for anon/service_role users only" ON "public"."api_keys" TO "anon", "service_role";

ALTER TABLE "public"."api_keys" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."depricated_uiuc_chatbot" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."doc_groups" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."documents" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."documents_doc_groups" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."documents_failed" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."documents_in_progress" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."documents_v2" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."email-newsletter" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."insights" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."llm-convo-monitor" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."n8n_workflows" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."nal_publications" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."projects" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."publications" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."uiuc-course-table" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."usage_metrics" ENABLE ROW LEVEL SECURITY;

ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";

REVOKE USAGE ON SCHEMA "public" FROM PUBLIC;
GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

GRANT ALL ON FUNCTION "public"."add_document_to_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "anon";
GRANT ALL ON FUNCTION "public"."add_document_to_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "authenticated";
GRANT ALL ON FUNCTION "public"."add_document_to_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "service_role";

GRANT ALL ON FUNCTION "public"."add_document_to_group_url"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "anon";
GRANT ALL ON FUNCTION "public"."add_document_to_group_url"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "authenticated";
GRANT ALL ON FUNCTION "public"."add_document_to_group_url"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "service_role";

GRANT ALL ON FUNCTION "public"."c"() TO "anon";
GRANT ALL ON FUNCTION "public"."c"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."c"() TO "service_role";

GRANT ALL ON FUNCTION "public"."check_and_lock_flows_v2"("id" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."check_and_lock_flows_v2"("id" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."check_and_lock_flows_v2"("id" integer) TO "service_role";

GRANT ALL ON FUNCTION "public"."cn"() TO "anon";
GRANT ALL ON FUNCTION "public"."cn"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."cn"() TO "service_role";

GRANT ALL ON FUNCTION "public"."get_course_names"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_course_names"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_course_names"() TO "service_role";

GRANT ALL ON FUNCTION "public"."get_distinct_course_names"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_distinct_course_names"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_distinct_course_names"() TO "service_role";

GRANT ALL ON FUNCTION "public"."get_latest_workflow_id"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_latest_workflow_id"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_latest_workflow_id"() TO "service_role";

GRANT ALL ON FUNCTION "public"."hello"() TO "anon";
GRANT ALL ON FUNCTION "public"."hello"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."hello"() TO "service_role";

GRANT ALL ON FUNCTION "public"."hypopg"(OUT "indexname" "text", OUT "indexrelid" "oid", OUT "indrelid" "oid", OUT "innatts" integer, OUT "indisunique" boolean, OUT "indkey" "int2vector", OUT "indcollation" "oidvector", OUT "indclass" "oidvector", OUT "indoption" "oidvector", OUT "indexprs" "pg_node_tree", OUT "indpred" "pg_node_tree", OUT "amid" "oid") TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg"(OUT "indexname" "text", OUT "indexrelid" "oid", OUT "indrelid" "oid", OUT "innatts" integer, OUT "indisunique" boolean, OUT "indkey" "int2vector", OUT "indcollation" "oidvector", OUT "indclass" "oidvector", OUT "indoption" "oidvector", OUT "indexprs" "pg_node_tree", OUT "indpred" "pg_node_tree", OUT "amid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg"(OUT "indexname" "text", OUT "indexrelid" "oid", OUT "indrelid" "oid", OUT "innatts" integer, OUT "indisunique" boolean, OUT "indkey" "int2vector", OUT "indcollation" "oidvector", OUT "indclass" "oidvector", OUT "indoption" "oidvector", OUT "indexprs" "pg_node_tree", OUT "indpred" "pg_node_tree", OUT "amid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg"(OUT "indexname" "text", OUT "indexrelid" "oid", OUT "indrelid" "oid", OUT "innatts" integer, OUT "indisunique" boolean, OUT "indkey" "int2vector", OUT "indcollation" "oidvector", OUT "indclass" "oidvector", OUT "indoption" "oidvector", OUT "indexprs" "pg_node_tree", OUT "indpred" "pg_node_tree", OUT "amid" "oid") TO "service_role";

GRANT ALL ON FUNCTION "public"."hypopg_create_index"("sql_order" "text", OUT "indexrelid" "oid", OUT "indexname" "text") TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_create_index"("sql_order" "text", OUT "indexrelid" "oid", OUT "indexname" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_create_index"("sql_order" "text", OUT "indexrelid" "oid", OUT "indexname" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_create_index"("sql_order" "text", OUT "indexrelid" "oid", OUT "indexname" "text") TO "service_role";

GRANT ALL ON FUNCTION "public"."hypopg_drop_index"("indexid" "oid") TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_drop_index"("indexid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_drop_index"("indexid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_drop_index"("indexid" "oid") TO "service_role";

GRANT ALL ON FUNCTION "public"."hypopg_get_indexdef"("indexid" "oid") TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_get_indexdef"("indexid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_get_indexdef"("indexid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_get_indexdef"("indexid" "oid") TO "service_role";

GRANT ALL ON FUNCTION "public"."hypopg_relation_size"("indexid" "oid") TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_relation_size"("indexid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_relation_size"("indexid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_relation_size"("indexid" "oid") TO "service_role";

GRANT ALL ON FUNCTION "public"."hypopg_reset"() TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_reset"() TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_reset"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_reset"() TO "service_role";

GRANT ALL ON FUNCTION "public"."hypopg_reset_index"() TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_reset_index"() TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_reset_index"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_reset_index"() TO "service_role";

GRANT ALL ON FUNCTION "public"."increment"("usage" integer, "apikey" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."increment"("usage" integer, "apikey" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."increment"("usage" integer, "apikey" "text") TO "service_role";

GRANT ALL ON FUNCTION "public"."increment_api_usage"("usage" integer, "apikey" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."increment_api_usage"("usage" integer, "apikey" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."increment_api_usage"("usage" integer, "apikey" "text") TO "service_role";

GRANT ALL ON FUNCTION "public"."increment_api_usage_count"("usage" integer, "apikey" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."increment_api_usage_count"("usage" integer, "apikey" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."increment_api_usage_count"("usage" integer, "apikey" "text") TO "service_role";

GRANT ALL ON FUNCTION "public"."increment_workflows"() TO "anon";
GRANT ALL ON FUNCTION "public"."increment_workflows"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."increment_workflows"() TO "service_role";

-- GRANT ALL ON FUNCTION "public"."index_advisor"("query" "text") TO "anon";
-- GRANT ALL ON FUNCTION "public"."index_advisor"("query" "text") TO "authenticated";
-- GRANT ALL ON FUNCTION "public"."index_advisor"("query" "text") TO "service_role";

GRANT ALL ON FUNCTION "public"."remove_document_from_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_doc_group" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."remove_document_from_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_doc_group" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."remove_document_from_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_doc_group" "text") TO "service_role";

GRANT ALL ON FUNCTION "public"."update_doc_count"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_doc_count"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_doc_count"() TO "service_role";

GRANT ALL ON TABLE "public"."api_keys" TO "anon";
GRANT ALL ON TABLE "public"."api_keys" TO "authenticated";
GRANT ALL ON TABLE "public"."api_keys" TO "service_role";

GRANT ALL ON TABLE "public"."course_names" TO "anon";
GRANT ALL ON TABLE "public"."course_names" TO "authenticated";
GRANT ALL ON TABLE "public"."course_names" TO "service_role";

GRANT ALL ON TABLE "public"."depricated_uiuc_chatbot" TO "anon";
GRANT ALL ON TABLE "public"."depricated_uiuc_chatbot" TO "authenticated";
GRANT ALL ON TABLE "public"."depricated_uiuc_chatbot" TO "service_role";

GRANT ALL ON TABLE "public"."documents" TO "anon";
GRANT ALL ON TABLE "public"."documents" TO "authenticated";
GRANT ALL ON TABLE "public"."documents" TO "service_role";

GRANT ALL ON TABLE "public"."distinct_course_names" TO "anon";
GRANT ALL ON TABLE "public"."distinct_course_names" TO "authenticated";
GRANT ALL ON TABLE "public"."distinct_course_names" TO "service_role";

GRANT ALL ON TABLE "public"."doc_groups" TO "anon";
GRANT ALL ON TABLE "public"."doc_groups" TO "authenticated";
GRANT ALL ON TABLE "public"."doc_groups" TO "service_role";

GRANT ALL ON SEQUENCE "public"."doc_groups_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."doc_groups_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."doc_groups_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."documents_doc_groups" TO "anon";
GRANT ALL ON TABLE "public"."documents_doc_groups" TO "authenticated";
GRANT ALL ON TABLE "public"."documents_doc_groups" TO "service_role";

GRANT ALL ON SEQUENCE "public"."documents_doc_groups_document_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."documents_doc_groups_document_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."documents_doc_groups_document_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."documents_failed" TO "anon";
GRANT ALL ON TABLE "public"."documents_failed" TO "authenticated";
GRANT ALL ON TABLE "public"."documents_failed" TO "service_role";

GRANT ALL ON SEQUENCE "public"."documents_failed_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."documents_failed_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."documents_failed_id_seq" TO "service_role";

GRANT ALL ON SEQUENCE "public"."documents_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."documents_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."documents_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."documents_in_progress" TO "anon";
GRANT ALL ON TABLE "public"."documents_in_progress" TO "authenticated";
GRANT ALL ON TABLE "public"."documents_in_progress" TO "service_role";

GRANT ALL ON SEQUENCE "public"."documents_in_progress_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."documents_in_progress_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."documents_in_progress_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."documents_v2" TO "anon";
GRANT ALL ON TABLE "public"."documents_v2" TO "authenticated";
GRANT ALL ON TABLE "public"."documents_v2" TO "service_role";

GRANT ALL ON SEQUENCE "public"."documents_v2_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."documents_v2_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."documents_v2_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."email-newsletter" TO "anon";
GRANT ALL ON TABLE "public"."email-newsletter" TO "authenticated";
GRANT ALL ON TABLE "public"."email-newsletter" TO "service_role";

GRANT ALL ON TABLE "public"."hypopg_list_indexes" TO "postgres";
GRANT ALL ON TABLE "public"."hypopg_list_indexes" TO "anon";
GRANT ALL ON TABLE "public"."hypopg_list_indexes" TO "authenticated";
GRANT ALL ON TABLE "public"."hypopg_list_indexes" TO "service_role";

GRANT ALL ON TABLE "public"."insights" TO "anon";
GRANT ALL ON TABLE "public"."insights" TO "authenticated";
GRANT ALL ON TABLE "public"."insights" TO "service_role";

GRANT ALL ON SEQUENCE "public"."insights_insight_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."insights_insight_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."insights_insight_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."llm-convo-monitor" TO "anon";
GRANT ALL ON TABLE "public"."llm-convo-monitor" TO "authenticated";
GRANT ALL ON TABLE "public"."llm-convo-monitor" TO "service_role";

GRANT ALL ON SEQUENCE "public"."llm-convo-monitor_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."llm-convo-monitor_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."llm-convo-monitor_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."n8n_workflows" TO "anon";
GRANT ALL ON TABLE "public"."n8n_workflows" TO "authenticated";
GRANT ALL ON TABLE "public"."n8n_workflows" TO "service_role";

GRANT ALL ON SEQUENCE "public"."n8n_api_keys_in_progress_workflow_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."n8n_api_keys_in_progress_workflow_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."n8n_api_keys_in_progress_workflow_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."nal_publications" TO "anon";
GRANT ALL ON TABLE "public"."nal_publications" TO "authenticated";
GRANT ALL ON TABLE "public"."nal_publications" TO "service_role";

GRANT ALL ON SEQUENCE "public"."nal_publications_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."nal_publications_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."nal_publications_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."projects" TO "anon";
GRANT ALL ON TABLE "public"."projects" TO "authenticated";
GRANT ALL ON TABLE "public"."projects" TO "service_role";

GRANT ALL ON SEQUENCE "public"."projects_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."projects_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."projects_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."publications" TO "anon";
GRANT ALL ON TABLE "public"."publications" TO "authenticated";
GRANT ALL ON TABLE "public"."publications" TO "service_role";

GRANT ALL ON SEQUENCE "public"."publications_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."publications_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."publications_id_seq" TO "service_role";

GRANT ALL ON SEQUENCE "public"."uiuc-chatbot_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."uiuc-chatbot_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."uiuc-chatbot_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."uiuc-course-table" TO "anon";
GRANT ALL ON TABLE "public"."uiuc-course-table" TO "authenticated";
GRANT ALL ON TABLE "public"."uiuc-course-table" TO "service_role";

GRANT ALL ON SEQUENCE "public"."uiuc-course-table_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."uiuc-course-table_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."uiuc-course-table_id_seq" TO "service_role";

GRANT ALL ON TABLE "public"."usage_metrics" TO "anon";
GRANT ALL ON TABLE "public"."usage_metrics" TO "authenticated";
GRANT ALL ON TABLE "public"."usage_metrics" TO "service_role";

GRANT ALL ON SEQUENCE "public"."usage_metrics_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."usage_metrics_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."usage_metrics_id_seq" TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES  TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS  TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES  TO "service_role";

RESET ALL;