

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


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_tle";






-- CREATE EXTENSION IF NOT EXISTS "supabase-dbdev" WITH SCHEMA "public";






CREATE SCHEMA IF NOT EXISTS "keycloak";


ALTER SCHEMA "keycloak" OWNER TO "postgres";


CREATE EXTENSION IF NOT EXISTS "pgsodium" WITH SCHEMA "pgsodium";






CREATE EXTENSION IF NOT EXISTS "http" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "hypopg" WITH SCHEMA "public";






CREATE EXTENSION IF NOT EXISTS "olirice-index_advisor" WITH SCHEMA "public";






CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pg_trgm" WITH SCHEMA "public";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgjwt" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE TYPE "public"."LLMProvider" AS ENUM (
    'Azure',
    'OpenAI',
    'Anthropic',
    'Ollama',
    'NCSAHosted',
    'WebLLM',
    'null'
);


ALTER TYPE "public"."LLMProvider" OWNER TO "postgres";


COMMENT ON TYPE "public"."LLMProvider" IS 'One of "azure", "openai", "anthropic", "google"... etc.';



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


CREATE OR REPLACE FUNCTION "public"."calculate_weekly_trends"("course_name_input" "text") RETURNS TABLE("metric_name" "text", "current_week_value" numeric, "previous_week_value" numeric, "percentage_change" numeric)
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    current_7_days_start DATE;
    previous_7_days_start DATE;
BEGIN
    -- Determine the start of the current 7-day period and the previous 7-day period
    current_7_days_start := CURRENT_DATE - INTERVAL '7 days';
    previous_7_days_start := CURRENT_DATE - INTERVAL '14 days';

    -- Debug: Log the date ranges
    RAISE NOTICE 'Current 7 Days: Start %, End %', current_7_days_start, CURRENT_DATE;
    RAISE NOTICE 'Previous 7 Days: Start %, End %', previous_7_days_start, current_7_days_start;

    -- Aggregate data for the 7-day periods
    RETURN QUERY
    WITH weekly_data AS (
        SELECT
            course_name,
            COUNT(DISTINCT user_email)::NUMERIC AS unique_users,
            COUNT(convo_id)::NUMERIC AS total_conversations,
            CASE
                WHEN created_at >= current_7_days_start AND created_at < CURRENT_DATE THEN 'current'
                WHEN created_at >= previous_7_days_start AND created_at < current_7_days_start THEN 'previous'
            END AS period
        FROM
            public."llm-convo-monitor"
        WHERE
            course_name = course_name_input
            AND created_at >= previous_7_days_start
            AND created_at < CURRENT_DATE
        GROUP BY
            course_name, period
    )
    -- Calculate trends for unique users
    SELECT
        'Unique Users' AS metric_name,
        COALESCE(current_data.unique_users, 0) AS current_week_value,
        COALESCE(previous_data.unique_users, 0) AS previous_week_value,
        CASE
            WHEN previous_data.unique_users = 0 THEN NULL
            ELSE ROUND(((current_data.unique_users - previous_data.unique_users) / previous_data.unique_users) * 100, 2)
        END AS percentage_change
    FROM
        (SELECT unique_users FROM weekly_data WHERE period = 'current') AS current_data
        FULL OUTER JOIN
        (SELECT unique_users FROM weekly_data WHERE period = 'previous') AS previous_data
        ON TRUE

    UNION ALL

    -- Calculate trends for total conversations
    SELECT
        'Total Conversations' AS metric_name,
        COALESCE(current_data.total_conversations, 0) AS current_week_value,
        COALESCE(previous_data.total_conversations, 0) AS previous_week_value,
        CASE
            WHEN previous_data.total_conversations = 0 THEN NULL
            ELSE ROUND(((current_data.total_conversations - previous_data.total_conversations) / previous_data.total_conversations) * 100, 2)
        END AS percentage_change
    FROM
        (SELECT total_conversations FROM weekly_data WHERE period = 'current') AS current_data
        FULL OUTER JOIN
        (SELECT total_conversations FROM weekly_data WHERE period = 'previous') AS previous_data
        ON TRUE;
END;
$$;


ALTER FUNCTION "public"."calculate_weekly_trends"("course_name_input" "text") OWNER TO "postgres";


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


CREATE OR REPLACE FUNCTION "public"."count_models_by_project"("project_name_input" "text") RETURNS TABLE("model" character varying, "count" bigint)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT conversations.model, COUNT(*) AS count
    FROM conversations
    WHERE conversations.project_name = project_name_input
    GROUP BY conversations.model
    ORDER BY count DESC;
END;
$$;


ALTER FUNCTION "public"."count_models_by_project"("project_name_input" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_base_url_with_doc_groups"("p_course_name" "text") RETURNS "json"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    result JSON;
BEGIN
    -- Aggregate base URLs and their respective group names into a JSON object
    SELECT JSON_OBJECT_AGG(base_url, group_names) INTO result
    FROM (
        SELECT 
            d.base_url, 
            COALESCE(JSON_AGG(DISTINCT dg.name) FILTER (WHERE dg.name IS NOT NULL AND dg.name != 'CropWizard Public'), '[]') AS group_names
        FROM public.documents d
        LEFT JOIN public.documents_doc_groups ddg ON d.id = ddg.document_id
        LEFT JOIN public.doc_groups dg ON ddg.doc_group_id = dg.id
        WHERE d.course_name = p_course_name
          AND d.base_url != ''
        GROUP BY d.base_url
    ) subquery;

    -- Return the final JSON object
    RETURN result;
END;$$;


ALTER FUNCTION "public"."get_base_url_with_doc_groups"("p_course_name" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_convo_maps"() RETURNS "json"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    course_details JSON;
BEGIN
    -- Aggregate course details into JSON format
    WITH filtered_courses AS (
        SELECT course_name
        FROM public."llm-convo-monitor"
        GROUP BY course_name
        HAVING COUNT(id) > 20
    )
    SELECT JSON_AGG(
        JSON_BUILD_OBJECT(
            'course_name', p.course_name,
            'convo_map_id', COALESCE(p.convo_map_id, 'N/A'),
            'last_uploaded_convo_id', COALESCE(p.last_uploaded_convo_id, 0)
        )
    ) INTO course_details
    FROM public.projects p
    JOIN filtered_courses fc ON p.course_name = fc.course_name
    WHERE p.course_name IS NOT NULL;

    -- Return the aggregated JSON
    RETURN course_details;
END;$$;


ALTER FUNCTION "public"."get_convo_maps"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_course_details"() RETURNS TABLE("course_name" "text", "convo_map_id" "text", "last_uploaded_convo_id" bigint)
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    RETURN QUERY
    SELECT p.course_name, p.convo_map_id, p.last_uploaded_convo_id
    FROM public."llm-convo-monitor" l
    JOIN public.projects p ON l.course_name = p.course_name
    GROUP BY p.course_name, p.convo_map_id, p.last_uploaded_convo_id
    HAVING COUNT(l.id) > 20;
END;
$$;


ALTER FUNCTION "public"."get_course_details"() OWNER TO "postgres";


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


CREATE OR REPLACE FUNCTION "public"."get_distinct_base_urls"("p_course_name" "text") RETURNS "json"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    distinct_base_urls JSON;
BEGIN
    -- Aggregate all distinct base URLs into an array
    SELECT JSON_AGG(DISTINCT d.base_url) INTO distinct_base_urls
    FROM public.documents d  -- Ensure d is correctly defined here
    WHERE d.course_name = p_course_name and d.base_url != '';

    --RAISE LOG 'distinct_course_names: %', distinct_base_urls;
    RETURN distinct_base_urls;
END;$$;


ALTER FUNCTION "public"."get_distinct_base_urls"("p_course_name" "text") OWNER TO "postgres";


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


CREATE OR REPLACE FUNCTION "public"."get_doc_map_details"() RETURNS "json"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    course_details JSON;
BEGIN
    -- Aggregate course details into JSON format
    WITH filtered_courses AS (
        SELECT course_name
        FROM public."documents"
        GROUP BY course_name
        HAVING COUNT(id) > 20
    )
    SELECT JSON_AGG(
        JSON_BUILD_OBJECT(
            'course_name', p.course_name,
            'doc_map_id', COALESCE(p.doc_map_id, 'N/A'),
            'last_uploaded_doc_id', COALESCE(p.last_uploaded_doc_id, 0)
        )
    ) INTO course_details
    FROM public.projects p
    JOIN filtered_courses fc ON p.course_name = fc.course_name
    WHERE p.course_name IS NOT NULL;

    -- Return the aggregated JSON
    RETURN course_details;
END;$$;


ALTER FUNCTION "public"."get_doc_map_details"() OWNER TO "postgres";


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


CREATE OR REPLACE FUNCTION "public"."get_run_data"("p_run_ids" "text", "p_limit" integer, "p_offset" integer) RETURNS "json"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    documents JSONB;
    v_limit INTEGER := COALESCE(p_limit, 10); -- Default limit is 10
    v_offset INTEGER := COALESCE(p_offset, 0); -- Default offset is 0
    v_run_ids INTEGER[] := STRING_TO_ARRAY(p_run_ids, ',')::INTEGER[]; -- Convert string to integer array
BEGIN
    WITH document_data AS (
        SELECT 
            cdm.run_id,
            cdm.document_id,
            c.readable_filename,
            cdm.field_name,
            cdm.field_value,
            cdm.created_at
        FROM cedar_documents c
        INNER JOIN cedar_document_metadata cdm 
        ON c.id = cdm.document_id
        WHERE cdm.run_id = ANY(v_run_ids) -- Dynamic filtering using converted array
        ORDER BY cdm.created_at DESC -- Optional: ordering by creation time
        LIMIT v_limit
        OFFSET v_offset
    )
    SELECT 
        jsonb_agg(
            jsonb_build_object(
                'run_id', dd.run_id,
                'document_id', dd.document_id,
                'readable_filename', dd.readable_filename,
                'field_name', dd.field_name,
                'field_value', dd.field_value,
                'created_at', dd.created_at
            )
        ) INTO documents
    FROM document_data dd;

    RETURN documents;
END;$$;


ALTER FUNCTION "public"."get_run_data"("p_run_ids" "text", "p_limit" integer, "p_offset" integer) OWNER TO "postgres";


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


CREATE OR REPLACE FUNCTION "public"."initialize_project_stats"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$BEGIN
    INSERT INTO public.project_stats (project_id, project_name, total_conversations, total_messages, unique_users)
    VALUES (NEW.id, NEW.course_name, 0, 0, 0);
    RETURN NEW;
END;$$;


ALTER FUNCTION "public"."initialize_project_stats"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."myfunc"() RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
begin
  set statement_timeout TO '600s'; -- set custom timeout;

  SELECT *
  FROM public.documents
  WHERE EXISTS (
    SELECT 1
    FROM jsonb_array_elements(contexts) AS elem
    WHERE elem->>'text' ILIKE '%We use cookies to provide you with the best possible experience. By continuing to use thi%'
  )
  LIMIT 5;
end;
$$;


ALTER FUNCTION "public"."myfunc"() OWNER TO "postgres";


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


CREATE OR REPLACE FUNCTION "public"."search_conversations"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text" DEFAULT NULL::"text", "p_limit" integer DEFAULT 10, "p_offset" integer DEFAULT 0) RETURNS "jsonb"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    total_count INT;
    conversations JSONB;
BEGIN
    -- Get the total count of conversations first
    SELECT COUNT(*) INTO total_count
    FROM public.conversations c
    WHERE c.user_email = p_user_email
    AND c.project_name = p_project_name
    AND c.folder_id IS NULL
    AND (
        p_search_term IS NULL 
        OR c.name ILIKE '%' || p_search_term || '%' 
        OR EXISTS (
            SELECT 1
            FROM public.messages m
            WHERE m.conversation_id = c.id
            AND m.content_text ILIKE '%' || p_search_term || '%'
        )
    );

    WITH conversation_data AS (
    SELECT 
        c.id AS conversation_id,
        c.name AS conversation_name,
        c.model,
        c.prompt,
        c.temperature,
        c.user_email,
        c.created_at AS conversation_created_at,
        c.updated_at AS conversation_updated_at,
        c.project_name,
        c.folder_id
    FROM public.conversations c
    WHERE c.user_email = p_user_email
    AND c.project_name = p_project_name
    AND c.folder_id IS NULL
    AND (
        p_search_term IS NULL 
        OR c.name ILIKE '%' || p_search_term || '%' 
        OR EXISTS (
            SELECT 1
            FROM public.messages m
            WHERE m.conversation_id = c.id
            AND m.content_text ILIKE '%' || p_search_term || '%'
        )
    )
    ORDER BY c.created_at DESC
    LIMIT p_limit OFFSET p_offset
)
SELECT 
    jsonb_build_object(
        'conversations', COALESCE(jsonb_agg(
            jsonb_build_object(
                'id', cd.conversation_id,
                'name', cd.conversation_name,
                'model', cd.model,
                'prompt', cd.prompt,
                'temperature', cd.temperature,
                'user_email', cd.user_email,
                'created_at', cd.conversation_created_at,
                'updated_at', cd.conversation_updated_at,
                'project_name', cd.project_name,
                'folder_id', cd.folder_id,
                'messages', (
                    SELECT COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'id', m.id,
                                'role', m.role,
                                'created_at', m.created_at,
                                'content_text', m.content_text,
                                'contexts', m.contexts,
                                'tools', m.tools,
                                'latest_system_message', m.latest_system_message,
                                'final_prompt_engineered_message', m.final_prompt_engineered_message,
                                'response_time_sec', m.response_time_sec,
                                'updated_at', m.updated_at,
                                'content_image_url', m.content_image_url,
                                'image_description', m.image_description
                            )
                            ORDER BY m.created_at ASC
                        ), '[]'::jsonb
                    )
                    FROM public.messages m
                    WHERE m.conversation_id = cd.conversation_id
                )
            )
        ), '[]'::jsonb),
        'total_count', total_count
    ) INTO conversations
FROM conversation_data cd;

    RETURN conversations;
END;$$;


ALTER FUNCTION "public"."search_conversations"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_conversations_v2"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    total_count INT;
    conversations JSONB;
    v_search_term text := COALESCE(p_search_term, NULL);
    v_limit integer := COALESCE(p_limit, 10);
    v_offset integer := COALESCE(p_offset, 0);
BEGIN
    -- Get the total count of conversations first
    SELECT COUNT(*) INTO total_count
    FROM public.conversations c
    WHERE c.user_email = p_user_email
    AND c.project_name = p_project_name
    AND c.folder_id IS NULL
    AND (
        v_search_term IS NULL 
        OR c.name ILIKE '%' || v_search_term || '%' 
        OR EXISTS (
            SELECT 1
            FROM public.messages m
            WHERE m.conversation_id = c.id
            AND m.content_text ILIKE '%' || v_search_term || '%'
        )
    );

    WITH conversation_data AS (
    SELECT 
        c.id AS conversation_id,
        c.name AS conversation_name,
        c.model,
        c.prompt,
        c.temperature,
        c.user_email,
        c.created_at AS conversation_created_at,
        c.updated_at AS conversation_updated_at,
        c.project_name,
        c.folder_id
    FROM public.conversations c
    WHERE c.user_email = p_user_email
    AND c.project_name = p_project_name
    AND c.folder_id IS NULL
    AND (
        v_search_term IS NULL 
        OR c.name ILIKE '%' || v_search_term || '%' 
        OR EXISTS (
            SELECT 1
            FROM public.messages m
            WHERE m.conversation_id = c.id
            AND m.content_text ILIKE '%' || v_search_term || '%'
        )
    )
    ORDER BY c.created_at DESC
    LIMIT v_limit OFFSET v_offset
)
SELECT 
    jsonb_build_object(
        'conversations', COALESCE(jsonb_agg(
            jsonb_build_object(
                'id', cd.conversation_id,
                'name', cd.conversation_name,
                'model', cd.model,
                'prompt', cd.prompt,
                'temperature', cd.temperature,
                'user_email', cd.user_email,
                'created_at', cd.conversation_created_at,
                'updated_at', cd.conversation_updated_at,
                'project_name', cd.project_name,
                'folder_id', cd.folder_id,
                'messages', (
                    SELECT COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'id', m.id,
                                'role', m.role,
                                'created_at', m.created_at,
                                'content_text', m.content_text,
                                'contexts', m.contexts,
                                'tools', m.tools,
                                'latest_system_message', m.latest_system_message,
                                'final_prompt_engineered_message', m.final_prompt_engineered_message,
                                'response_time_sec', m.response_time_sec,
                                'updated_at', m.updated_at,
                                'content_image_url', m.content_image_url,
                                'image_description', m.image_description,
                                'feedback', (
                                    CASE 
                                        WHEN m.feedback_is_positive IS NOT NULL 
                                        THEN jsonb_build_object(
                                            'feedback_is_positive', m.feedback_is_positive,
                                            'feedback_category', m.feedback_category,
                                            'feedback_details', m.feedback_details
                                        )
                                        ELSE NULL
                                    END
                                )
                            )
                            ORDER BY m.created_at ASC
                        ), '[]'::jsonb
                    )
                    FROM public.messages m
                    WHERE m.conversation_id = cd.conversation_id
                )
            )
        ), '[]'::jsonb),
        'total_count', total_count
    ) INTO conversations
FROM conversation_data cd;

    RETURN conversations;
END;$$;


ALTER FUNCTION "public"."search_conversations_v2"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."search_conversations_v3"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) RETURNS "jsonb"
    LANGUAGE "plpgsql"
    AS $$DECLARE
    total_count INT;
    conversations JSONB;
    v_search_term text := COALESCE(p_search_term, NULL);
    v_limit integer := COALESCE(p_limit, 10);
    v_offset integer := COALESCE(p_offset, 0);
BEGIN
    -- Get the total count of conversations first
    SELECT COUNT(*) INTO total_count
    FROM public.conversations c
    WHERE c.user_email = p_user_email
    AND c.project_name = p_project_name
    AND c.folder_id IS NULL
    AND (
        v_search_term IS NULL 
        OR c.name ILIKE '%' || v_search_term || '%' 
        OR EXISTS (
            SELECT 1
            FROM public.messages m
            WHERE m.conversation_id = c.id
            AND m.content_text ILIKE '%' || v_search_term || '%'
        )
    );

    WITH conversation_data AS (
    SELECT 
        c.id AS conversation_id,
        c.name AS conversation_name,
        c.model,
        c.prompt,
        c.temperature,
        c.user_email,
        c.created_at AS conversation_created_at,
        c.updated_at AS conversation_updated_at,
        c.project_name,
        c.folder_id
    FROM public.conversations c
    WHERE c.user_email = p_user_email
    AND c.project_name = p_project_name
    AND c.folder_id IS NULL
    AND (
        v_search_term IS NULL 
        OR c.name ILIKE '%' || v_search_term || '%' 
        OR EXISTS (
            SELECT 1
            FROM public.messages m
            WHERE m.conversation_id = c.id
            AND m.content_text ILIKE '%' || v_search_term || '%'
        )
    )
    ORDER BY c.created_at DESC
    LIMIT v_limit OFFSET v_offset
)
SELECT 
    jsonb_build_object(
        'conversations', COALESCE(jsonb_agg(
            jsonb_build_object(
                'id', cd.conversation_id,
                'name', cd.conversation_name,
                'model', cd.model,
                'prompt', cd.prompt,
                'temperature', cd.temperature,
                'user_email', cd.user_email,
                'created_at', cd.conversation_created_at,
                'updated_at', cd.conversation_updated_at,
                'project_name', cd.project_name,
                'folder_id', cd.folder_id,
                'messages', (
                    SELECT COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'id', m.id,
                                'role', m.role,
                                'created_at', m.created_at,
                                'content_text', m.content_text,
                                'contexts', m.contexts,
                                'tools', m.tools,
                                'latest_system_message', m.latest_system_message,
                                'final_prompt_engineered_message', m.final_prompt_engineered_message,
                                'response_time_sec', m.response_time_sec,
                                'updated_at', m.updated_at,
                                'content_image_url', m.content_image_url,
                                'image_description', m.image_description,
                                'was_query_rewritten', m.was_query_rewritten,
                                'query_rewrite_text', m.query_rewrite_text,
                                'feedback', (
                                    CASE 
                                        WHEN m.feedback_is_positive IS NOT NULL 
                                        THEN jsonb_build_object(
                                            'feedback_is_positive', m.feedback_is_positive,
                                            'feedback_category', m.feedback_category,
                                            'feedback_details', m.feedback_details
                                        )
                                        ELSE NULL
                                    END
                                )
                            )
                            ORDER BY m.created_at ASC
                        ), '[]'::jsonb
                    )
                    FROM public.messages m
                    WHERE m.conversation_id = cd.conversation_id
                )
            )
        ), '[]'::jsonb),
        'total_count', total_count
    ) INTO conversations
FROM conversation_data cd;

    RETURN conversations;
END;$$;


ALTER FUNCTION "public"."search_conversations_v3"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."test_function"("id" integer) RETURNS "text"
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
        -- update public.n8n_workflows
        -- set latest_workflow_id = id,
        -- is_locked = True
        -- where latest_workflow_id = workflow_id;
        return 'Workflow updated';

    
    end if;
end;$$;


ALTER FUNCTION "public"."test_function"("id" integer) OWNER TO "postgres";


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


CREATE OR REPLACE FUNCTION "public"."update_project_stats"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    new_conversation_message_count INT;
    updated_distinct_user_count INT;
    old_message_count INT;
    new_message_count INT;
BEGIN
    
    IF TG_OP = 'INSERT' THEN

        -- Calculate message count for the new conversation
        SELECT COUNT(*)
        INTO new_conversation_message_count
        FROM json_array_elements(NEW.convo->'messages') AS message
        WHERE message->>'role' = 'user';

        -- Calculate distinct user count after the insert
        SELECT COUNT(DISTINCT user_email)
        INTO updated_distinct_user_count
        FROM public."llm-convo-monitor"
        WHERE course_name = NEW.course_name;

        -- Update project_stats with new conversation and distinct users
        UPDATE public.project_stats
        SET total_conversations = COALESCE(total_conversations, 0) + 1,
            total_messages = COALESCE(total_messages, 0) + new_conversation_message_count,
            unique_users = updated_distinct_user_count
        WHERE project_name = NEW.course_name;

    ELSIF TG_OP = 'UPDATE' THEN
        -- Get old and new message counts
        SELECT COUNT(*)
        INTO old_message_count
        FROM json_array_elements(OLD.convo->'messages') AS message
        WHERE message->>'role' = 'user';

        SELECT COUNT(*)
        INTO new_message_count
        FROM json_array_elements(NEW.convo->'messages') AS message
        WHERE message->>'role' = 'user';

        -- Update only message count if conversation content changed
        UPDATE public.project_stats
        SET total_messages = COALESCE(total_messages, 0) - old_message_count + new_message_count
        WHERE project_name = NEW.course_name;

    ELSIF TG_OP = 'DELETE' THEN
        -- Calculate message count of deleted conversation
        SELECT COUNT(*)
        INTO old_message_count
        FROM json_array_elements(OLD.convo->'messages') AS message
        WHERE message->>'role' = 'user';

        -- Calculate distinct user count after the delete
        SELECT COUNT(DISTINCT user_email)
        INTO updated_distinct_user_count
        FROM public."llm-convo-monitor"
        WHERE course_name = OLD.course_name;

        -- Update project_stats for deleted conversation and messages
        UPDATE public.project_stats
        SET total_conversations = COALESCE(total_conversations, 0) - 1,
            total_messages = COALESCE(total_messages, 0) - old_message_count,
            unique_users = updated_distinct_user_count
        WHERE project_name = OLD.course_name;
    END IF;

    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$;


ALTER FUNCTION "public"."update_project_stats"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_total_messages_by_id_range"("start_id" integer, "end_id" integer) RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    project RECORD;
BEGIN
    -- Loop through projects within the specified id range in project_stats
    FOR project IN
        SELECT id, project_name
        FROM public.project_stats
        WHERE id BETWEEN start_id AND end_id
        ORDER BY id
    LOOP
        -- Update total messages for each project in the specified range
        UPDATE public.project_stats ps
        SET total_messages = (
            SELECT COALESCE(SUM(
                (SELECT COUNT(*)
                 FROM json_array_elements(lcm.convo->'messages') AS message
                 WHERE message->>'role' = 'user')
            ), 0)
            FROM public."llm-convo-monitor" lcm
            WHERE lcm.course_name = project.project_name
        )
        WHERE ps.id = project.id
        AND EXISTS (
            SELECT 1 FROM public."llm-convo-monitor" lcm
            WHERE lcm.course_name = project.project_name
        );

        -- Set total_messages to 0 if no conversations exist for the project
        UPDATE public.project_stats ps
        SET total_messages = 0
        WHERE ps.id = project.id
        AND NOT EXISTS (
            SELECT 1 FROM public."llm-convo-monitor" lcm
            WHERE lcm.course_name = project.project_name
        );

        -- Optional: Display progress
        RAISE NOTICE 'Updated total_messages for project: % with id: %', project.project_name, project.id;
    END LOOP;
END;
$$;


ALTER FUNCTION "public"."update_total_messages_by_id_range"("start_id" integer, "end_id" integer) OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "keycloak"."admin_event_entity" (
    "id" character varying(36) NOT NULL,
    "admin_event_time" bigint,
    "realm_id" character varying(255),
    "operation_type" character varying(255),
    "auth_realm_id" character varying(255),
    "auth_client_id" character varying(255),
    "auth_user_id" character varying(255),
    "ip_address" character varying(255),
    "resource_path" character varying(2550),
    "representation" "text",
    "error" character varying(255),
    "resource_type" character varying(64)
);


ALTER TABLE "keycloak"."admin_event_entity" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."associated_policy" (
    "policy_id" character varying(36) NOT NULL,
    "associated_policy_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."associated_policy" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."authentication_execution" (
    "id" character varying(36) NOT NULL,
    "alias" character varying(255),
    "authenticator" character varying(36),
    "realm_id" character varying(36),
    "flow_id" character varying(36),
    "requirement" integer,
    "priority" integer,
    "authenticator_flow" boolean DEFAULT false NOT NULL,
    "auth_flow_id" character varying(36),
    "auth_config" character varying(36)
);


ALTER TABLE "keycloak"."authentication_execution" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."authentication_flow" (
    "id" character varying(36) NOT NULL,
    "alias" character varying(255),
    "description" character varying(255),
    "realm_id" character varying(36),
    "provider_id" character varying(36) DEFAULT 'basic-flow'::character varying NOT NULL,
    "top_level" boolean DEFAULT false NOT NULL,
    "built_in" boolean DEFAULT false NOT NULL
);


ALTER TABLE "keycloak"."authentication_flow" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."authenticator_config" (
    "id" character varying(36) NOT NULL,
    "alias" character varying(255),
    "realm_id" character varying(36)
);


ALTER TABLE "keycloak"."authenticator_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."authenticator_config_entry" (
    "authenticator_id" character varying(36) NOT NULL,
    "value" "text",
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."authenticator_config_entry" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."broker_link" (
    "identity_provider" character varying(255) NOT NULL,
    "storage_provider_id" character varying(255),
    "realm_id" character varying(36) NOT NULL,
    "broker_user_id" character varying(255),
    "broker_username" character varying(255),
    "token" "text",
    "user_id" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."broker_link" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client" (
    "id" character varying(36) NOT NULL,
    "enabled" boolean DEFAULT false NOT NULL,
    "full_scope_allowed" boolean DEFAULT false NOT NULL,
    "client_id" character varying(255),
    "not_before" integer,
    "public_client" boolean DEFAULT false NOT NULL,
    "secret" character varying(255),
    "base_url" character varying(255),
    "bearer_only" boolean DEFAULT false NOT NULL,
    "management_url" character varying(255),
    "surrogate_auth_required" boolean DEFAULT false NOT NULL,
    "realm_id" character varying(36),
    "protocol" character varying(255),
    "node_rereg_timeout" integer DEFAULT 0,
    "frontchannel_logout" boolean DEFAULT false NOT NULL,
    "consent_required" boolean DEFAULT false NOT NULL,
    "name" character varying(255),
    "service_accounts_enabled" boolean DEFAULT false NOT NULL,
    "client_authenticator_type" character varying(255),
    "root_url" character varying(255),
    "description" character varying(255),
    "registration_token" character varying(255),
    "standard_flow_enabled" boolean DEFAULT true NOT NULL,
    "implicit_flow_enabled" boolean DEFAULT false NOT NULL,
    "direct_access_grants_enabled" boolean DEFAULT false NOT NULL,
    "always_display_in_console" boolean DEFAULT false NOT NULL
);


ALTER TABLE "keycloak"."client" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_attributes" (
    "client_id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "value" "text"
);


ALTER TABLE "keycloak"."client_attributes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_auth_flow_bindings" (
    "client_id" character varying(36) NOT NULL,
    "flow_id" character varying(36),
    "binding_name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."client_auth_flow_bindings" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_initial_access" (
    "id" character varying(36) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "timestamp" integer,
    "expiration" integer,
    "count" integer,
    "remaining_count" integer
);


ALTER TABLE "keycloak"."client_initial_access" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_node_registrations" (
    "client_id" character varying(36) NOT NULL,
    "value" integer,
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."client_node_registrations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_scope" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255),
    "realm_id" character varying(36),
    "description" character varying(255),
    "protocol" character varying(255)
);


ALTER TABLE "keycloak"."client_scope" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_scope_attributes" (
    "scope_id" character varying(36) NOT NULL,
    "value" character varying(2048),
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."client_scope_attributes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_scope_client" (
    "client_id" character varying(255) NOT NULL,
    "scope_id" character varying(255) NOT NULL,
    "default_scope" boolean DEFAULT false NOT NULL
);


ALTER TABLE "keycloak"."client_scope_client" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_scope_role_mapping" (
    "scope_id" character varying(36) NOT NULL,
    "role_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."client_scope_role_mapping" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_session" (
    "id" character varying(36) NOT NULL,
    "client_id" character varying(36),
    "redirect_uri" character varying(255),
    "state" character varying(255),
    "timestamp" integer,
    "session_id" character varying(36),
    "auth_method" character varying(255),
    "realm_id" character varying(255),
    "auth_user_id" character varying(36),
    "current_action" character varying(36)
);


ALTER TABLE "keycloak"."client_session" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_session_auth_status" (
    "authenticator" character varying(36) NOT NULL,
    "status" integer,
    "client_session" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."client_session_auth_status" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_session_note" (
    "name" character varying(255) NOT NULL,
    "value" character varying(255),
    "client_session" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."client_session_note" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_session_prot_mapper" (
    "protocol_mapper_id" character varying(36) NOT NULL,
    "client_session" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."client_session_prot_mapper" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_session_role" (
    "role_id" character varying(255) NOT NULL,
    "client_session" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."client_session_role" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."client_user_session_note" (
    "name" character varying(255) NOT NULL,
    "value" character varying(2048),
    "client_session" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."client_user_session_note" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."component" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255),
    "parent_id" character varying(36),
    "provider_id" character varying(36),
    "provider_type" character varying(255),
    "realm_id" character varying(36),
    "sub_type" character varying(255)
);


ALTER TABLE "keycloak"."component" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."component_config" (
    "id" character varying(36) NOT NULL,
    "component_id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "value" "text"
);


ALTER TABLE "keycloak"."component_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."composite_role" (
    "composite" character varying(36) NOT NULL,
    "child_role" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."composite_role" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."credential" (
    "id" character varying(36) NOT NULL,
    "salt" "bytea",
    "type" character varying(255),
    "user_id" character varying(36),
    "created_date" bigint,
    "user_label" character varying(255),
    "secret_data" "text",
    "credential_data" "text",
    "priority" integer
);


ALTER TABLE "keycloak"."credential" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."databasechangelog" (
    "id" character varying(255) NOT NULL,
    "author" character varying(255) NOT NULL,
    "filename" character varying(255) NOT NULL,
    "dateexecuted" timestamp without time zone NOT NULL,
    "orderexecuted" integer NOT NULL,
    "exectype" character varying(10) NOT NULL,
    "md5sum" character varying(35),
    "description" character varying(255),
    "comments" character varying(255),
    "tag" character varying(255),
    "liquibase" character varying(20),
    "contexts" character varying(255),
    "labels" character varying(255),
    "deployment_id" character varying(10)
);


ALTER TABLE "keycloak"."databasechangelog" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."databasechangeloglock" (
    "id" integer NOT NULL,
    "locked" boolean NOT NULL,
    "lockgranted" timestamp without time zone,
    "lockedby" character varying(255)
);


ALTER TABLE "keycloak"."databasechangeloglock" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."default_client_scope" (
    "realm_id" character varying(36) NOT NULL,
    "scope_id" character varying(36) NOT NULL,
    "default_scope" boolean DEFAULT false NOT NULL
);


ALTER TABLE "keycloak"."default_client_scope" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."event_entity" (
    "id" character varying(36) NOT NULL,
    "client_id" character varying(255),
    "details_json" character varying(2550),
    "error" character varying(255),
    "ip_address" character varying(255),
    "realm_id" character varying(255),
    "session_id" character varying(255),
    "event_time" bigint,
    "type" character varying(255),
    "user_id" character varying(255),
    "details_json_long_value" "text"
);


ALTER TABLE "keycloak"."event_entity" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."fed_user_attribute" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "user_id" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "storage_provider_id" character varying(36),
    "value" character varying(2024),
    "long_value_hash" "bytea",
    "long_value_hash_lower_case" "bytea",
    "long_value" "text"
);


ALTER TABLE "keycloak"."fed_user_attribute" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."fed_user_consent" (
    "id" character varying(36) NOT NULL,
    "client_id" character varying(255),
    "user_id" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "storage_provider_id" character varying(36),
    "created_date" bigint,
    "last_updated_date" bigint,
    "client_storage_provider" character varying(36),
    "external_client_id" character varying(255)
);


ALTER TABLE "keycloak"."fed_user_consent" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."fed_user_consent_cl_scope" (
    "user_consent_id" character varying(36) NOT NULL,
    "scope_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."fed_user_consent_cl_scope" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."fed_user_credential" (
    "id" character varying(36) NOT NULL,
    "salt" "bytea",
    "type" character varying(255),
    "created_date" bigint,
    "user_id" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "storage_provider_id" character varying(36),
    "user_label" character varying(255),
    "secret_data" "text",
    "credential_data" "text",
    "priority" integer
);


ALTER TABLE "keycloak"."fed_user_credential" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."fed_user_group_membership" (
    "group_id" character varying(36) NOT NULL,
    "user_id" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "storage_provider_id" character varying(36)
);


ALTER TABLE "keycloak"."fed_user_group_membership" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."fed_user_required_action" (
    "required_action" character varying(255) DEFAULT ' '::character varying NOT NULL,
    "user_id" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "storage_provider_id" character varying(36)
);


ALTER TABLE "keycloak"."fed_user_required_action" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."fed_user_role_mapping" (
    "role_id" character varying(36) NOT NULL,
    "user_id" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "storage_provider_id" character varying(36)
);


ALTER TABLE "keycloak"."fed_user_role_mapping" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."federated_identity" (
    "identity_provider" character varying(255) NOT NULL,
    "realm_id" character varying(36),
    "federated_user_id" character varying(255),
    "federated_username" character varying(255),
    "token" "text",
    "user_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."federated_identity" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."federated_user" (
    "id" character varying(255) NOT NULL,
    "storage_provider_id" character varying(255),
    "realm_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."federated_user" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."group_attribute" (
    "id" character varying(36) DEFAULT 'sybase-needs-something-here'::character varying NOT NULL,
    "name" character varying(255) NOT NULL,
    "value" character varying(255),
    "group_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."group_attribute" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."group_role_mapping" (
    "role_id" character varying(36) NOT NULL,
    "group_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."group_role_mapping" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."identity_provider" (
    "internal_id" character varying(36) NOT NULL,
    "enabled" boolean DEFAULT false NOT NULL,
    "provider_alias" character varying(255),
    "provider_id" character varying(255),
    "store_token" boolean DEFAULT false NOT NULL,
    "authenticate_by_default" boolean DEFAULT false NOT NULL,
    "realm_id" character varying(36),
    "add_token_role" boolean DEFAULT true NOT NULL,
    "trust_email" boolean DEFAULT false NOT NULL,
    "first_broker_login_flow_id" character varying(36),
    "post_broker_login_flow_id" character varying(36),
    "provider_display_name" character varying(255),
    "link_only" boolean DEFAULT false NOT NULL
);


ALTER TABLE "keycloak"."identity_provider" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."identity_provider_config" (
    "identity_provider_id" character varying(36) NOT NULL,
    "value" "text",
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."identity_provider_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."identity_provider_mapper" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "idp_alias" character varying(255) NOT NULL,
    "idp_mapper_name" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."identity_provider_mapper" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."idp_mapper_config" (
    "idp_mapper_id" character varying(36) NOT NULL,
    "value" "text",
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."idp_mapper_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."keycloak_group" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255),
    "parent_group" character varying(36) NOT NULL,
    "realm_id" character varying(36)
);


ALTER TABLE "keycloak"."keycloak_group" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."keycloak_role" (
    "id" character varying(36) NOT NULL,
    "client_realm_constraint" character varying(255),
    "client_role" boolean DEFAULT false NOT NULL,
    "description" character varying(255),
    "name" character varying(255),
    "realm_id" character varying(255),
    "client" character varying(36),
    "realm" character varying(36)
);


ALTER TABLE "keycloak"."keycloak_role" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."migration_model" (
    "id" character varying(36) NOT NULL,
    "version" character varying(36),
    "update_time" bigint DEFAULT 0 NOT NULL
);


ALTER TABLE "keycloak"."migration_model" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."offline_client_session" (
    "user_session_id" character varying(36) NOT NULL,
    "client_id" character varying(255) NOT NULL,
    "offline_flag" character varying(4) NOT NULL,
    "timestamp" integer,
    "data" "text",
    "client_storage_provider" character varying(36) DEFAULT 'local'::character varying NOT NULL,
    "external_client_id" character varying(255) DEFAULT 'local'::character varying NOT NULL,
    "version" integer DEFAULT 0
);


ALTER TABLE "keycloak"."offline_client_session" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."offline_user_session" (
    "user_session_id" character varying(36) NOT NULL,
    "user_id" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "created_on" integer NOT NULL,
    "offline_flag" character varying(4) NOT NULL,
    "data" "text",
    "last_session_refresh" integer DEFAULT 0 NOT NULL,
    "broker_session_id" character varying(1024),
    "version" integer DEFAULT 0
);


ALTER TABLE "keycloak"."offline_user_session" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."org" (
    "id" character varying(255) NOT NULL,
    "enabled" boolean NOT NULL,
    "realm_id" character varying(255) NOT NULL,
    "group_id" character varying(255) NOT NULL,
    "name" character varying(255) NOT NULL,
    "description" character varying(4000)
);


ALTER TABLE "keycloak"."org" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."org_domain" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "verified" boolean NOT NULL,
    "org_id" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."org_domain" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."policy_config" (
    "policy_id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "value" "text"
);


ALTER TABLE "keycloak"."policy_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."protocol_mapper" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "protocol" character varying(255) NOT NULL,
    "protocol_mapper_name" character varying(255) NOT NULL,
    "client_id" character varying(36),
    "client_scope_id" character varying(36)
);


ALTER TABLE "keycloak"."protocol_mapper" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."protocol_mapper_config" (
    "protocol_mapper_id" character varying(36) NOT NULL,
    "value" "text",
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."protocol_mapper_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm" (
    "id" character varying(36) NOT NULL,
    "access_code_lifespan" integer,
    "user_action_lifespan" integer,
    "access_token_lifespan" integer,
    "account_theme" character varying(255),
    "admin_theme" character varying(255),
    "email_theme" character varying(255),
    "enabled" boolean DEFAULT false NOT NULL,
    "events_enabled" boolean DEFAULT false NOT NULL,
    "events_expiration" bigint,
    "login_theme" character varying(255),
    "name" character varying(255),
    "not_before" integer,
    "password_policy" character varying(2550),
    "registration_allowed" boolean DEFAULT false NOT NULL,
    "remember_me" boolean DEFAULT false NOT NULL,
    "reset_password_allowed" boolean DEFAULT false NOT NULL,
    "social" boolean DEFAULT false NOT NULL,
    "ssl_required" character varying(255),
    "sso_idle_timeout" integer,
    "sso_max_lifespan" integer,
    "update_profile_on_soc_login" boolean DEFAULT false NOT NULL,
    "verify_email" boolean DEFAULT false NOT NULL,
    "master_admin_client" character varying(36),
    "login_lifespan" integer,
    "internationalization_enabled" boolean DEFAULT false NOT NULL,
    "default_locale" character varying(255),
    "reg_email_as_username" boolean DEFAULT false NOT NULL,
    "admin_events_enabled" boolean DEFAULT false NOT NULL,
    "admin_events_details_enabled" boolean DEFAULT false NOT NULL,
    "edit_username_allowed" boolean DEFAULT false NOT NULL,
    "otp_policy_counter" integer DEFAULT 0,
    "otp_policy_window" integer DEFAULT 1,
    "otp_policy_period" integer DEFAULT 30,
    "otp_policy_digits" integer DEFAULT 6,
    "otp_policy_alg" character varying(36) DEFAULT 'HmacSHA1'::character varying,
    "otp_policy_type" character varying(36) DEFAULT 'totp'::character varying,
    "browser_flow" character varying(36),
    "registration_flow" character varying(36),
    "direct_grant_flow" character varying(36),
    "reset_credentials_flow" character varying(36),
    "client_auth_flow" character varying(36),
    "offline_session_idle_timeout" integer DEFAULT 0,
    "revoke_refresh_token" boolean DEFAULT false NOT NULL,
    "access_token_life_implicit" integer DEFAULT 0,
    "login_with_email_allowed" boolean DEFAULT true NOT NULL,
    "duplicate_emails_allowed" boolean DEFAULT false NOT NULL,
    "docker_auth_flow" character varying(36),
    "refresh_token_max_reuse" integer DEFAULT 0,
    "allow_user_managed_access" boolean DEFAULT false NOT NULL,
    "sso_max_lifespan_remember_me" integer DEFAULT 0 NOT NULL,
    "sso_idle_timeout_remember_me" integer DEFAULT 0 NOT NULL,
    "default_role" character varying(255)
);


ALTER TABLE "keycloak"."realm" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm_attribute" (
    "name" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL,
    "value" "text"
);


ALTER TABLE "keycloak"."realm_attribute" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm_default_groups" (
    "realm_id" character varying(36) NOT NULL,
    "group_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."realm_default_groups" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm_enabled_event_types" (
    "realm_id" character varying(36) NOT NULL,
    "value" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."realm_enabled_event_types" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm_events_listeners" (
    "realm_id" character varying(36) NOT NULL,
    "value" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."realm_events_listeners" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm_localizations" (
    "realm_id" character varying(255) NOT NULL,
    "locale" character varying(255) NOT NULL,
    "texts" "text" NOT NULL
);


ALTER TABLE "keycloak"."realm_localizations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm_required_credential" (
    "type" character varying(255) NOT NULL,
    "form_label" character varying(255),
    "input" boolean DEFAULT false NOT NULL,
    "secret" boolean DEFAULT false NOT NULL,
    "realm_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."realm_required_credential" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm_smtp_config" (
    "realm_id" character varying(36) NOT NULL,
    "value" character varying(255),
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."realm_smtp_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."realm_supported_locales" (
    "realm_id" character varying(36) NOT NULL,
    "value" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."realm_supported_locales" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."redirect_uris" (
    "client_id" character varying(36) NOT NULL,
    "value" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."redirect_uris" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."required_action_config" (
    "required_action_id" character varying(36) NOT NULL,
    "value" "text",
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."required_action_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."required_action_provider" (
    "id" character varying(36) NOT NULL,
    "alias" character varying(255),
    "name" character varying(255),
    "realm_id" character varying(36),
    "enabled" boolean DEFAULT false NOT NULL,
    "default_action" boolean DEFAULT false NOT NULL,
    "provider_id" character varying(255),
    "priority" integer
);


ALTER TABLE "keycloak"."required_action_provider" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_attribute" (
    "id" character varying(36) DEFAULT 'sybase-needs-something-here'::character varying NOT NULL,
    "name" character varying(255) NOT NULL,
    "value" character varying(255),
    "resource_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."resource_attribute" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_policy" (
    "resource_id" character varying(36) NOT NULL,
    "policy_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."resource_policy" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_scope" (
    "resource_id" character varying(36) NOT NULL,
    "scope_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."resource_scope" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_server" (
    "id" character varying(36) NOT NULL,
    "allow_rs_remote_mgmt" boolean DEFAULT false NOT NULL,
    "policy_enforce_mode" smallint NOT NULL,
    "decision_strategy" smallint DEFAULT 1 NOT NULL
);


ALTER TABLE "keycloak"."resource_server" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_server_perm_ticket" (
    "id" character varying(36) NOT NULL,
    "owner" character varying(255) NOT NULL,
    "requester" character varying(255) NOT NULL,
    "created_timestamp" bigint NOT NULL,
    "granted_timestamp" bigint,
    "resource_id" character varying(36) NOT NULL,
    "scope_id" character varying(36),
    "resource_server_id" character varying(36) NOT NULL,
    "policy_id" character varying(36)
);


ALTER TABLE "keycloak"."resource_server_perm_ticket" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_server_policy" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "description" character varying(255),
    "type" character varying(255) NOT NULL,
    "decision_strategy" smallint,
    "logic" smallint,
    "resource_server_id" character varying(36) NOT NULL,
    "owner" character varying(255)
);


ALTER TABLE "keycloak"."resource_server_policy" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_server_resource" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "type" character varying(255),
    "icon_uri" character varying(255),
    "owner" character varying(255) NOT NULL,
    "resource_server_id" character varying(36) NOT NULL,
    "owner_managed_access" boolean DEFAULT false NOT NULL,
    "display_name" character varying(255)
);


ALTER TABLE "keycloak"."resource_server_resource" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_server_scope" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "icon_uri" character varying(255),
    "resource_server_id" character varying(36) NOT NULL,
    "display_name" character varying(255)
);


ALTER TABLE "keycloak"."resource_server_scope" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."resource_uris" (
    "resource_id" character varying(36) NOT NULL,
    "value" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."resource_uris" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."role_attribute" (
    "id" character varying(36) NOT NULL,
    "role_id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "value" character varying(255)
);


ALTER TABLE "keycloak"."role_attribute" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."scope_mapping" (
    "client_id" character varying(36) NOT NULL,
    "role_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."scope_mapping" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."scope_policy" (
    "scope_id" character varying(36) NOT NULL,
    "policy_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."scope_policy" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_attribute" (
    "name" character varying(255) NOT NULL,
    "value" character varying(255),
    "user_id" character varying(36) NOT NULL,
    "id" character varying(36) DEFAULT 'sybase-needs-something-here'::character varying NOT NULL,
    "long_value_hash" "bytea",
    "long_value_hash_lower_case" "bytea",
    "long_value" "text"
);


ALTER TABLE "keycloak"."user_attribute" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_consent" (
    "id" character varying(36) NOT NULL,
    "client_id" character varying(255),
    "user_id" character varying(36) NOT NULL,
    "created_date" bigint,
    "last_updated_date" bigint,
    "client_storage_provider" character varying(36),
    "external_client_id" character varying(255)
);


ALTER TABLE "keycloak"."user_consent" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_consent_client_scope" (
    "user_consent_id" character varying(36) NOT NULL,
    "scope_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."user_consent_client_scope" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_entity" (
    "id" character varying(36) NOT NULL,
    "email" character varying(255),
    "email_constraint" character varying(255),
    "email_verified" boolean DEFAULT false NOT NULL,
    "enabled" boolean DEFAULT false NOT NULL,
    "federation_link" character varying(255),
    "first_name" character varying(255),
    "last_name" character varying(255),
    "realm_id" character varying(255),
    "username" character varying(255),
    "created_timestamp" bigint,
    "service_account_client_link" character varying(255),
    "not_before" integer DEFAULT 0 NOT NULL
);


ALTER TABLE "keycloak"."user_entity" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_federation_config" (
    "user_federation_provider_id" character varying(36) NOT NULL,
    "value" character varying(255),
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."user_federation_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_federation_mapper" (
    "id" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "federation_provider_id" character varying(36) NOT NULL,
    "federation_mapper_type" character varying(255) NOT NULL,
    "realm_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."user_federation_mapper" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_federation_mapper_config" (
    "user_federation_mapper_id" character varying(36) NOT NULL,
    "value" character varying(255),
    "name" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."user_federation_mapper_config" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_federation_provider" (
    "id" character varying(36) NOT NULL,
    "changed_sync_period" integer,
    "display_name" character varying(255),
    "full_sync_period" integer,
    "last_sync" integer,
    "priority" integer,
    "provider_name" character varying(255),
    "realm_id" character varying(36)
);


ALTER TABLE "keycloak"."user_federation_provider" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_group_membership" (
    "group_id" character varying(36) NOT NULL,
    "user_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."user_group_membership" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_required_action" (
    "user_id" character varying(36) NOT NULL,
    "required_action" character varying(255) DEFAULT ' '::character varying NOT NULL
);


ALTER TABLE "keycloak"."user_required_action" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_role_mapping" (
    "role_id" character varying(255) NOT NULL,
    "user_id" character varying(36) NOT NULL
);


ALTER TABLE "keycloak"."user_role_mapping" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_session" (
    "id" character varying(36) NOT NULL,
    "auth_method" character varying(255),
    "ip_address" character varying(255),
    "last_session_refresh" integer,
    "login_username" character varying(255),
    "realm_id" character varying(255),
    "remember_me" boolean DEFAULT false NOT NULL,
    "started" integer,
    "user_id" character varying(255),
    "user_session_state" integer,
    "broker_session_id" character varying(255),
    "broker_user_id" character varying(255)
);


ALTER TABLE "keycloak"."user_session" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."user_session_note" (
    "user_session" character varying(36) NOT NULL,
    "name" character varying(255) NOT NULL,
    "value" character varying(2048)
);


ALTER TABLE "keycloak"."user_session_note" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."username_login_failure" (
    "realm_id" character varying(36) NOT NULL,
    "username" character varying(255) NOT NULL,
    "failed_login_not_before" integer,
    "last_failure" bigint,
    "last_ip_failure" character varying(255),
    "num_failures" integer
);


ALTER TABLE "keycloak"."username_login_failure" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "keycloak"."web_origins" (
    "client_id" character varying(36) NOT NULL,
    "value" character varying(255) NOT NULL
);


ALTER TABLE "keycloak"."web_origins" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."api_keys" (
    "user_id" "text" NOT NULL,
    "key" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "modified_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "usage_count" bigint DEFAULT '0'::bigint NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL,
    "keycloak_id" character varying(255)
);


ALTER TABLE "public"."api_keys" OWNER TO "postgres";


COMMENT ON COLUMN "public"."api_keys"."user_id" IS 'User ID from Clerk auth';



CREATE TABLE IF NOT EXISTS "public"."cedar_chunks" (
    "id" bigint NOT NULL,
    "document_id" integer NOT NULL,
    "segment_id" integer,
    "chunk_number" integer NOT NULL,
    "chunk_type" "text" NOT NULL,
    "content" "text" NOT NULL,
    "table_html" "text",
    "table_image_paths" "text"[],
    "table_data" "json",
    "chunk_metadata" "json",
    "orig_elements" "text",
    "created_at" timestamp without time zone NOT NULL
);


ALTER TABLE "public"."cedar_chunks" OWNER TO "postgres";


ALTER TABLE "public"."cedar_chunks" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."cedar_chunks_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."cedar_document_metadata" (
    "id" integer NOT NULL,
    "document_id" integer NOT NULL,
    "field_name" character varying NOT NULL,
    "field_value" "json",
    "confidence_score" integer,
    "extraction_method" character varying,
    "created_at" timestamp without time zone DEFAULT "now"() NOT NULL,
    "run_id" bigint,
    "prompt" "text"
);


ALTER TABLE "public"."cedar_document_metadata" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."cedar_document_metadata_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."cedar_document_metadata_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."cedar_document_metadata_id_seq" OWNED BY "public"."cedar_document_metadata"."id";



CREATE TABLE IF NOT EXISTS "public"."cedar_documents" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "course_name" character varying,
    "readable_filename" character varying,
    "s3_path" character varying,
    "url" character varying,
    "base_url" character varying,
    "last_error" character varying
);


ALTER TABLE "public"."cedar_documents" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."cedar_documents_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE "public"."cedar_documents_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."cedar_documents_id_seq" OWNED BY "public"."cedar_documents"."id";



ALTER TABLE "public"."cedar_documents" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."cedar_documents_id_seq1"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."cedar_runs" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "run_id" bigint NOT NULL,
    "document_id" integer,
    "readable_filename" character varying,
    "run_status" character varying,
    "last_error" character varying,
    "prompt" "text"
);


ALTER TABLE "public"."cedar_runs" OWNER TO "postgres";


ALTER TABLE "public"."cedar_runs" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."cedar_runs_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."conversations" (
    "id" "uuid" NOT NULL,
    "name" character varying(255) NOT NULL,
    "model" character varying(100) NOT NULL,
    "prompt" "text" NOT NULL,
    "temperature" double precision NOT NULL,
    "user_email" character varying(255),
    "created_at" timestamp with time zone NOT NULL,
    "updated_at" timestamp with time zone NOT NULL,
    "project_name" "text" DEFAULT ''::"text" NOT NULL,
    "folder_id" "uuid"
);


ALTER TABLE "public"."conversations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."course_names" (
    "course_name" "text"
);


ALTER TABLE "public"."course_names" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cropwizard-papers" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "doi" "text",
    "publisher" "text",
    "license" "text",
    "metadata" "jsonb"
);


ALTER TABLE "public"."cropwizard-papers" OWNER TO "postgres";


COMMENT ON TABLE "public"."cropwizard-papers" IS 'Metadata about research papers ingested in cropwizard';



ALTER TABLE "public"."cropwizard-papers" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."cropwizard-papers_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



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



CREATE TABLE IF NOT EXISTS "public"."doc_groups_sharing" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "destination_project_id" bigint,
    "doc_group_id" bigint,
    "destination_project_name" character varying,
    "doc_group_name" "text"
);


ALTER TABLE "public"."doc_groups_sharing" OWNER TO "postgres";


COMMENT ON TABLE "public"."doc_groups_sharing" IS '`Source` - the document group being cloned. `Destination` - the project doing the cloning. e.g. Cropwizard (Source) is cloned into Industry Partner project (Destination).';



ALTER TABLE "public"."doc_groups_sharing" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."doc_groups_sharing_id_seq"
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



CREATE TABLE IF NOT EXISTS "public"."email-newsletter" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "email" "text",
    "unsubscribed-from-newsletter" boolean
);


ALTER TABLE "public"."email-newsletter" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."folders" (
    "id" "uuid" NOT NULL,
    "name" character varying(255) NOT NULL,
    "user_email" character varying(255) NOT NULL,
    "created_at" timestamp with time zone DEFAULT ("now"() AT TIME ZONE 'utc'::"text") NOT NULL,
    "type" "text",
    "updated_at" timestamp with time zone DEFAULT ("now"() AT TIME ZONE 'utc'::"text")
);


ALTER TABLE "public"."folders" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."llm-convo-monitor" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "convo" "json",
    "convo_id" "text",
    "course_name" "text",
    "user_email" "text",
    "summary" "text",
    "convo_analysis_tags" "jsonb"
);


ALTER TABLE "public"."llm-convo-monitor" OWNER TO "postgres";


COMMENT ON COLUMN "public"."llm-convo-monitor"."convo_id" IS 'id from Conversation object in Typescript.';



COMMENT ON COLUMN "public"."llm-convo-monitor"."user_email" IS 'The users'' email address (first email only, if they have multiple)';



COMMENT ON COLUMN "public"."llm-convo-monitor"."summary" IS 'Running summary of conversation';



COMMENT ON COLUMN "public"."llm-convo-monitor"."convo_analysis_tags" IS 'A json array of tags / categories that an LLM has tagged this conversation with.';



ALTER TABLE "public"."llm-convo-monitor" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."llm-convo-monitor_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."llm-guided-contexts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "text" "text",
    "num_tokens" "text",
    "stop_reason" "text",
    "doc_id" "uuid",
    "section_id" "uuid"
);


ALTER TABLE "public"."llm-guided-contexts" OWNER TO "postgres";


COMMENT ON TABLE "public"."llm-guided-contexts" IS 'PROTOTYPE';



COMMENT ON COLUMN "public"."llm-guided-contexts"."doc_id" IS 'A foreign key to the document ID';



COMMENT ON COLUMN "public"."llm-guided-contexts"."section_id" IS 'A foreign key link to the appropriate doc section.';



CREATE TABLE IF NOT EXISTS "public"."llm-guided-docs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "num_tokens" bigint,
    "date_published" timestamp with time zone,
    "authors" "text",
    "outline" "text",
    "minio_path" "text",
    "title" "text"
);


ALTER TABLE "public"."llm-guided-docs" OWNER TO "postgres";


COMMENT ON TABLE "public"."llm-guided-docs" IS 'PROTOTYPE ONLY.';



COMMENT ON COLUMN "public"."llm-guided-docs"."title" IS 'Document title.';



CREATE TABLE IF NOT EXISTS "public"."llm-guided-sections" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "num_tokens" bigint,
    "section_title" "text",
    "section_num" "text",
    "doc_id" "uuid"
);


ALTER TABLE "public"."llm-guided-sections" OWNER TO "postgres";


COMMENT ON TABLE "public"."llm-guided-sections" IS 'PROTOTYPE ONLY';



COMMENT ON COLUMN "public"."llm-guided-sections"."section_num" IS 'Could be a section number or the name of a biblography references to a paper & authors. i.e. BIBREF0 and section-title will be the full text citation.';



CREATE TABLE IF NOT EXISTS "public"."messages" (
    "id" "uuid" NOT NULL,
    "conversation_id" "uuid",
    "role" character varying(50) NOT NULL,
    "created_at" timestamp with time zone NOT NULL,
    "content_text" "text" NOT NULL,
    "contexts" "jsonb",
    "tools" "jsonb",
    "latest_system_message" "text",
    "final_prompt_engineered_message" "text",
    "response_time_sec" integer,
    "updated_at" timestamp with time zone,
    "content_image_url" "text"[],
    "image_description" "text",
    "feedback_is_positive" boolean,
    "feedback_category" "text",
    "feedback_details" "text",
    "was_query_rewritten" boolean,
    "query_rewrite_text" "text",
    "processed_content" "text"
);


ALTER TABLE "public"."messages" OWNER TO "postgres";


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
    "link" "text",
    "ingested" boolean DEFAULT false NOT NULL,
    "downloadable" boolean DEFAULT true NOT NULL,
    "notes" "text",
    "modified_date" timestamp without time zone DEFAULT "now"()
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



CREATE TABLE IF NOT EXISTS "public"."pre_authorized_api_keys" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "providerBodyNoModels" "jsonb",
    "emails" "jsonb",
    "providerName" "public"."LLMProvider",
    "notes" "text"
);


ALTER TABLE "public"."pre_authorized_api_keys" OWNER TO "postgres";


COMMENT ON TABLE "public"."pre_authorized_api_keys" IS 'These users have access to pre-authorized API keys';



COMMENT ON COLUMN "public"."pre_authorized_api_keys"."providerBodyNoModels" IS 'The given LLM Provider''s Body JSON, with everything EXCEPT models, which will be grabbed dynamically.';



COMMENT ON COLUMN "public"."pre_authorized_api_keys"."providerName" IS 'One of "azure", "openai", "anthropic", "google"... etc.';



COMMENT ON COLUMN "public"."pre_authorized_api_keys"."notes" IS 'Just general reference info';



ALTER TABLE "public"."pre_authorized_api_keys" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."pre-authorized-api-keys_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."project_stats" (
    "id" bigint NOT NULL,
    "project_id" bigint,
    "project_name" character varying,
    "total_conversations" bigint DEFAULT '0'::bigint,
    "total_messages" bigint DEFAULT '0'::bigint,
    "unique_users" bigint DEFAULT '0'::bigint,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "model_usage_counts" "jsonb"
);


ALTER TABLE "public"."project_stats" OWNER TO "postgres";


ALTER TABLE "public"."project_stats" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."project_stats_id_seq"
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
    "metadata_schema" "json",
    "conversation_map_index" "text",
    "document_map_index" "text"
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



CREATE TABLE IF NOT EXISTS "public"."pubmed_daily_update" (
    "id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "last_xml_file" "text",
    "status" "text"
);


ALTER TABLE "public"."pubmed_daily_update" OWNER TO "postgres";


COMMENT ON TABLE "public"."pubmed_daily_update" IS 'Table to keep track of all the XML files we have processed';



ALTER TABLE "public"."pubmed_daily_update" ALTER COLUMN "id" ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME "public"."pubmed_daily_update_id_seq"
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



ALTER TABLE ONLY "public"."cedar_document_metadata" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."cedar_document_metadata_id_seq"'::"regclass");



ALTER TABLE ONLY "keycloak"."username_login_failure"
    ADD CONSTRAINT "CONSTRAINT_17-2" PRIMARY KEY ("realm_id", "username");



ALTER TABLE ONLY "keycloak"."org_domain"
    ADD CONSTRAINT "ORG_DOMAIN_pkey" PRIMARY KEY ("id", "name");



ALTER TABLE ONLY "keycloak"."org"
    ADD CONSTRAINT "ORG_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."keycloak_role"
    ADD CONSTRAINT "UK_J3RWUVD56ONTGSUHOGM184WW2-2" UNIQUE ("name", "client_realm_constraint");



ALTER TABLE ONLY "keycloak"."client_auth_flow_bindings"
    ADD CONSTRAINT "c_cli_flow_bind" PRIMARY KEY ("client_id", "binding_name");



ALTER TABLE ONLY "keycloak"."client_scope_client"
    ADD CONSTRAINT "c_cli_scope_bind" PRIMARY KEY ("client_id", "scope_id");



ALTER TABLE ONLY "keycloak"."client_initial_access"
    ADD CONSTRAINT "cnstr_client_init_acc_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."realm_default_groups"
    ADD CONSTRAINT "con_group_id_def_groups" UNIQUE ("group_id");



ALTER TABLE ONLY "keycloak"."broker_link"
    ADD CONSTRAINT "constr_broker_link_pk" PRIMARY KEY ("identity_provider", "user_id");



ALTER TABLE ONLY "keycloak"."client_user_session_note"
    ADD CONSTRAINT "constr_cl_usr_ses_note" PRIMARY KEY ("client_session", "name");



ALTER TABLE ONLY "keycloak"."component_config"
    ADD CONSTRAINT "constr_component_config_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."component"
    ADD CONSTRAINT "constr_component_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."fed_user_required_action"
    ADD CONSTRAINT "constr_fed_required_action" PRIMARY KEY ("required_action", "user_id");



ALTER TABLE ONLY "keycloak"."fed_user_attribute"
    ADD CONSTRAINT "constr_fed_user_attr_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."fed_user_consent"
    ADD CONSTRAINT "constr_fed_user_consent_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."fed_user_credential"
    ADD CONSTRAINT "constr_fed_user_cred_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."fed_user_group_membership"
    ADD CONSTRAINT "constr_fed_user_group" PRIMARY KEY ("group_id", "user_id");



ALTER TABLE ONLY "keycloak"."fed_user_role_mapping"
    ADD CONSTRAINT "constr_fed_user_role" PRIMARY KEY ("role_id", "user_id");



ALTER TABLE ONLY "keycloak"."federated_user"
    ADD CONSTRAINT "constr_federated_user" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."realm_default_groups"
    ADD CONSTRAINT "constr_realm_default_groups" PRIMARY KEY ("realm_id", "group_id");



ALTER TABLE ONLY "keycloak"."realm_enabled_event_types"
    ADD CONSTRAINT "constr_realm_enabl_event_types" PRIMARY KEY ("realm_id", "value");



ALTER TABLE ONLY "keycloak"."realm_events_listeners"
    ADD CONSTRAINT "constr_realm_events_listeners" PRIMARY KEY ("realm_id", "value");



ALTER TABLE ONLY "keycloak"."realm_supported_locales"
    ADD CONSTRAINT "constr_realm_supported_locales" PRIMARY KEY ("realm_id", "value");



ALTER TABLE ONLY "keycloak"."identity_provider"
    ADD CONSTRAINT "constraint_2b" PRIMARY KEY ("internal_id");



ALTER TABLE ONLY "keycloak"."client_attributes"
    ADD CONSTRAINT "constraint_3c" PRIMARY KEY ("client_id", "name");



ALTER TABLE ONLY "keycloak"."event_entity"
    ADD CONSTRAINT "constraint_4" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."federated_identity"
    ADD CONSTRAINT "constraint_40" PRIMARY KEY ("identity_provider", "user_id");



ALTER TABLE ONLY "keycloak"."realm"
    ADD CONSTRAINT "constraint_4a" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."client_session_role"
    ADD CONSTRAINT "constraint_5" PRIMARY KEY ("client_session", "role_id");



ALTER TABLE ONLY "keycloak"."user_session"
    ADD CONSTRAINT "constraint_57" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."user_federation_provider"
    ADD CONSTRAINT "constraint_5c" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."client_session_note"
    ADD CONSTRAINT "constraint_5e" PRIMARY KEY ("client_session", "name");



ALTER TABLE ONLY "keycloak"."client"
    ADD CONSTRAINT "constraint_7" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."client_session"
    ADD CONSTRAINT "constraint_8" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."scope_mapping"
    ADD CONSTRAINT "constraint_81" PRIMARY KEY ("client_id", "role_id");



ALTER TABLE ONLY "keycloak"."client_node_registrations"
    ADD CONSTRAINT "constraint_84" PRIMARY KEY ("client_id", "name");



ALTER TABLE ONLY "keycloak"."realm_attribute"
    ADD CONSTRAINT "constraint_9" PRIMARY KEY ("name", "realm_id");



ALTER TABLE ONLY "keycloak"."realm_required_credential"
    ADD CONSTRAINT "constraint_92" PRIMARY KEY ("realm_id", "type");



ALTER TABLE ONLY "keycloak"."keycloak_role"
    ADD CONSTRAINT "constraint_a" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."admin_event_entity"
    ADD CONSTRAINT "constraint_admin_event_entity" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."authenticator_config_entry"
    ADD CONSTRAINT "constraint_auth_cfg_pk" PRIMARY KEY ("authenticator_id", "name");



ALTER TABLE ONLY "keycloak"."authentication_execution"
    ADD CONSTRAINT "constraint_auth_exec_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."authentication_flow"
    ADD CONSTRAINT "constraint_auth_flow_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."authenticator_config"
    ADD CONSTRAINT "constraint_auth_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."client_session_auth_status"
    ADD CONSTRAINT "constraint_auth_status_pk" PRIMARY KEY ("client_session", "authenticator");



ALTER TABLE ONLY "keycloak"."user_role_mapping"
    ADD CONSTRAINT "constraint_c" PRIMARY KEY ("role_id", "user_id");



ALTER TABLE ONLY "keycloak"."composite_role"
    ADD CONSTRAINT "constraint_composite_role" PRIMARY KEY ("composite", "child_role");



ALTER TABLE ONLY "keycloak"."client_session_prot_mapper"
    ADD CONSTRAINT "constraint_cs_pmp_pk" PRIMARY KEY ("client_session", "protocol_mapper_id");



ALTER TABLE ONLY "keycloak"."identity_provider_config"
    ADD CONSTRAINT "constraint_d" PRIMARY KEY ("identity_provider_id", "name");



ALTER TABLE ONLY "keycloak"."policy_config"
    ADD CONSTRAINT "constraint_dpc" PRIMARY KEY ("policy_id", "name");



ALTER TABLE ONLY "keycloak"."realm_smtp_config"
    ADD CONSTRAINT "constraint_e" PRIMARY KEY ("realm_id", "name");



ALTER TABLE ONLY "keycloak"."credential"
    ADD CONSTRAINT "constraint_f" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."user_federation_config"
    ADD CONSTRAINT "constraint_f9" PRIMARY KEY ("user_federation_provider_id", "name");



ALTER TABLE ONLY "keycloak"."resource_server_perm_ticket"
    ADD CONSTRAINT "constraint_fapmt" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."resource_server_resource"
    ADD CONSTRAINT "constraint_farsr" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."resource_server_policy"
    ADD CONSTRAINT "constraint_farsrp" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."associated_policy"
    ADD CONSTRAINT "constraint_farsrpap" PRIMARY KEY ("policy_id", "associated_policy_id");



ALTER TABLE ONLY "keycloak"."resource_policy"
    ADD CONSTRAINT "constraint_farsrpp" PRIMARY KEY ("resource_id", "policy_id");



ALTER TABLE ONLY "keycloak"."resource_server_scope"
    ADD CONSTRAINT "constraint_farsrs" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."resource_scope"
    ADD CONSTRAINT "constraint_farsrsp" PRIMARY KEY ("resource_id", "scope_id");



ALTER TABLE ONLY "keycloak"."scope_policy"
    ADD CONSTRAINT "constraint_farsrsps" PRIMARY KEY ("scope_id", "policy_id");



ALTER TABLE ONLY "keycloak"."user_entity"
    ADD CONSTRAINT "constraint_fb" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."user_federation_mapper_config"
    ADD CONSTRAINT "constraint_fedmapper_cfg_pm" PRIMARY KEY ("user_federation_mapper_id", "name");



ALTER TABLE ONLY "keycloak"."user_federation_mapper"
    ADD CONSTRAINT "constraint_fedmapperpm" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."fed_user_consent_cl_scope"
    ADD CONSTRAINT "constraint_fgrntcsnt_clsc_pm" PRIMARY KEY ("user_consent_id", "scope_id");



ALTER TABLE ONLY "keycloak"."user_consent_client_scope"
    ADD CONSTRAINT "constraint_grntcsnt_clsc_pm" PRIMARY KEY ("user_consent_id", "scope_id");



ALTER TABLE ONLY "keycloak"."user_consent"
    ADD CONSTRAINT "constraint_grntcsnt_pm" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."keycloak_group"
    ADD CONSTRAINT "constraint_group" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."group_attribute"
    ADD CONSTRAINT "constraint_group_attribute_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."group_role_mapping"
    ADD CONSTRAINT "constraint_group_role" PRIMARY KEY ("role_id", "group_id");



ALTER TABLE ONLY "keycloak"."identity_provider_mapper"
    ADD CONSTRAINT "constraint_idpm" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."idp_mapper_config"
    ADD CONSTRAINT "constraint_idpmconfig" PRIMARY KEY ("idp_mapper_id", "name");



ALTER TABLE ONLY "keycloak"."migration_model"
    ADD CONSTRAINT "constraint_migmod" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."offline_client_session"
    ADD CONSTRAINT "constraint_offl_cl_ses_pk3" PRIMARY KEY ("user_session_id", "client_id", "client_storage_provider", "external_client_id", "offline_flag");



ALTER TABLE ONLY "keycloak"."offline_user_session"
    ADD CONSTRAINT "constraint_offl_us_ses_pk2" PRIMARY KEY ("user_session_id", "offline_flag");



ALTER TABLE ONLY "keycloak"."protocol_mapper"
    ADD CONSTRAINT "constraint_pcm" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."protocol_mapper_config"
    ADD CONSTRAINT "constraint_pmconfig" PRIMARY KEY ("protocol_mapper_id", "name");



ALTER TABLE ONLY "keycloak"."redirect_uris"
    ADD CONSTRAINT "constraint_redirect_uris" PRIMARY KEY ("client_id", "value");



ALTER TABLE ONLY "keycloak"."required_action_config"
    ADD CONSTRAINT "constraint_req_act_cfg_pk" PRIMARY KEY ("required_action_id", "name");



ALTER TABLE ONLY "keycloak"."required_action_provider"
    ADD CONSTRAINT "constraint_req_act_prv_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."user_required_action"
    ADD CONSTRAINT "constraint_required_action" PRIMARY KEY ("required_action", "user_id");



ALTER TABLE ONLY "keycloak"."resource_uris"
    ADD CONSTRAINT "constraint_resour_uris_pk" PRIMARY KEY ("resource_id", "value");



ALTER TABLE ONLY "keycloak"."role_attribute"
    ADD CONSTRAINT "constraint_role_attribute_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."user_attribute"
    ADD CONSTRAINT "constraint_user_attribute_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."user_group_membership"
    ADD CONSTRAINT "constraint_user_group" PRIMARY KEY ("group_id", "user_id");



ALTER TABLE ONLY "keycloak"."user_session_note"
    ADD CONSTRAINT "constraint_usn_pk" PRIMARY KEY ("user_session", "name");



ALTER TABLE ONLY "keycloak"."web_origins"
    ADD CONSTRAINT "constraint_web_origins" PRIMARY KEY ("client_id", "value");



ALTER TABLE ONLY "keycloak"."databasechangeloglock"
    ADD CONSTRAINT "databasechangeloglock_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."client_scope_attributes"
    ADD CONSTRAINT "pk_cl_tmpl_attr" PRIMARY KEY ("scope_id", "name");



ALTER TABLE ONLY "keycloak"."client_scope"
    ADD CONSTRAINT "pk_cli_template" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."resource_server"
    ADD CONSTRAINT "pk_resource_server" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."client_scope_role_mapping"
    ADD CONSTRAINT "pk_template_scope" PRIMARY KEY ("scope_id", "role_id");



ALTER TABLE ONLY "keycloak"."default_client_scope"
    ADD CONSTRAINT "r_def_cli_scope_bind" PRIMARY KEY ("realm_id", "scope_id");



ALTER TABLE ONLY "keycloak"."realm_localizations"
    ADD CONSTRAINT "realm_localizations_pkey" PRIMARY KEY ("realm_id", "locale");



ALTER TABLE ONLY "keycloak"."resource_attribute"
    ADD CONSTRAINT "res_attr_pk" PRIMARY KEY ("id");



ALTER TABLE ONLY "keycloak"."keycloak_group"
    ADD CONSTRAINT "sibling_names" UNIQUE ("realm_id", "parent_group", "name");



ALTER TABLE ONLY "keycloak"."identity_provider"
    ADD CONSTRAINT "uk_2daelwnibji49avxsrtuf6xj33" UNIQUE ("provider_alias", "realm_id");



ALTER TABLE ONLY "keycloak"."client"
    ADD CONSTRAINT "uk_b71cjlbenv945rb6gcon438at" UNIQUE ("realm_id", "client_id");



ALTER TABLE ONLY "keycloak"."client_scope"
    ADD CONSTRAINT "uk_cli_scope" UNIQUE ("realm_id", "name");



ALTER TABLE ONLY "keycloak"."user_entity"
    ADD CONSTRAINT "uk_dykn684sl8up1crfei6eckhd7" UNIQUE ("realm_id", "email_constraint");



ALTER TABLE ONLY "keycloak"."user_consent"
    ADD CONSTRAINT "uk_external_consent" UNIQUE ("client_storage_provider", "external_client_id", "user_id");



ALTER TABLE ONLY "keycloak"."resource_server_resource"
    ADD CONSTRAINT "uk_frsr6t700s9v50bu18ws5ha6" UNIQUE ("name", "owner", "resource_server_id");



ALTER TABLE ONLY "keycloak"."resource_server_perm_ticket"
    ADD CONSTRAINT "uk_frsr6t700s9v50bu18ws5pmt" UNIQUE ("owner", "requester", "resource_server_id", "resource_id", "scope_id");



ALTER TABLE ONLY "keycloak"."resource_server_policy"
    ADD CONSTRAINT "uk_frsrpt700s9v50bu18ws5ha6" UNIQUE ("name", "resource_server_id");



ALTER TABLE ONLY "keycloak"."resource_server_scope"
    ADD CONSTRAINT "uk_frsrst700s9v50bu18ws5ha6" UNIQUE ("name", "resource_server_id");



ALTER TABLE ONLY "keycloak"."user_consent"
    ADD CONSTRAINT "uk_local_consent" UNIQUE ("client_id", "user_id");



ALTER TABLE ONLY "keycloak"."org"
    ADD CONSTRAINT "uk_org_group" UNIQUE ("group_id");



ALTER TABLE ONLY "keycloak"."org"
    ADD CONSTRAINT "uk_org_name" UNIQUE ("realm_id", "name");



ALTER TABLE ONLY "keycloak"."realm"
    ADD CONSTRAINT "uk_orvsdmla56612eaefiq6wl5oi" UNIQUE ("name");



ALTER TABLE ONLY "keycloak"."user_entity"
    ADD CONSTRAINT "uk_ru8tt6t700s9v50bu18ws5ha6" UNIQUE ("realm_id", "username");



ALTER TABLE ONLY "public"."api_keys"
    ADD CONSTRAINT "api_keys_pkey" PRIMARY KEY ("user_id");



ALTER TABLE ONLY "public"."cedar_chunks"
    ADD CONSTRAINT "cedar_chunks_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cedar_document_metadata"
    ADD CONSTRAINT "cedar_document_metadata_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cedar_documents"
    ADD CONSTRAINT "cedar_documents_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cedar_runs"
    ADD CONSTRAINT "cedar_runs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."conversations"
    ADD CONSTRAINT "conversations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cropwizard-papers"
    ADD CONSTRAINT "cropwizard-papers_doi_key" UNIQUE ("doi");



ALTER TABLE ONLY "public"."cropwizard-papers"
    ADD CONSTRAINT "cropwizard-papers_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."doc_groups"
    ADD CONSTRAINT "doc_groups_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."doc_groups_sharing"
    ADD CONSTRAINT "doc_groups_sharing_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."llm-guided-docs"
    ADD CONSTRAINT "docs-llm-guided_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."documents_doc_groups"
    ADD CONSTRAINT "documents_doc_groups_pkey" PRIMARY KEY ("document_id", "doc_group_id");



ALTER TABLE ONLY "public"."documents_failed"
    ADD CONSTRAINT "documents_failed_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."documents_in_progress"
    ADD CONSTRAINT "documents_in_progress_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."documents"
    ADD CONSTRAINT "documents_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."email-newsletter"
    ADD CONSTRAINT "email-newsletter_email_key" UNIQUE ("email");



ALTER TABLE ONLY "public"."email-newsletter"
    ADD CONSTRAINT "email-newsletter_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."folders"
    ADD CONSTRAINT "folders_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."llm-convo-monitor"
    ADD CONSTRAINT "llm-convo-monitor_convo_id_key" UNIQUE ("convo_id");



ALTER TABLE ONLY "public"."llm-convo-monitor"
    ADD CONSTRAINT "llm-convo-monitor_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."llm-guided-contexts"
    ADD CONSTRAINT "llm-guided-contexts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."llm-guided-docs"
    ADD CONSTRAINT "llm-guided-docs_id_key" UNIQUE ("id");



ALTER TABLE ONLY "public"."llm-guided-sections"
    ADD CONSTRAINT "llm-guided-sections_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."n8n_workflows"
    ADD CONSTRAINT "n8n_api_keys_pkey" PRIMARY KEY ("latest_workflow_id");



ALTER TABLE ONLY "public"."nal_publications"
    ADD CONSTRAINT "nal_publications_doi_key" UNIQUE ("doi");



ALTER TABLE ONLY "public"."nal_publications"
    ADD CONSTRAINT "nal_publications_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."pre_authorized_api_keys"
    ADD CONSTRAINT "pre-authorized-api-keys_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."project_stats"
    ADD CONSTRAINT "project_stats_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."project_stats"
    ADD CONSTRAINT "project_stats_project_name_key" UNIQUE ("project_name");



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_course_name_key" UNIQUE ("course_name");



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."publications"
    ADD CONSTRAINT "publications_id_key" UNIQUE ("id");



ALTER TABLE ONLY "public"."publications"
    ADD CONSTRAINT "publications_pkey" PRIMARY KEY ("pmid");



ALTER TABLE ONLY "public"."pubmed_daily_update"
    ADD CONSTRAINT "pubmed_daily_update_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."depricated_uiuc_chatbot"
    ADD CONSTRAINT "uiuc-chatbot_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."uiuc-course-table"
    ADD CONSTRAINT "uiuc-course-table_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."doc_groups"
    ADD CONSTRAINT "unique_name_course_name" UNIQUE ("name", "course_name");



ALTER TABLE ONLY "public"."usage_metrics"
    ADD CONSTRAINT "usage_metrics_pkey" PRIMARY KEY ("id");



CREATE INDEX "fed_user_attr_long_values" ON "keycloak"."fed_user_attribute" USING "btree" ("long_value_hash", "name");



CREATE INDEX "fed_user_attr_long_values_lower_case" ON "keycloak"."fed_user_attribute" USING "btree" ("long_value_hash_lower_case", "name");



CREATE INDEX "idx_admin_event_time" ON "keycloak"."admin_event_entity" USING "btree" ("realm_id", "admin_event_time");



CREATE INDEX "idx_assoc_pol_assoc_pol_id" ON "keycloak"."associated_policy" USING "btree" ("associated_policy_id");



CREATE INDEX "idx_auth_config_realm" ON "keycloak"."authenticator_config" USING "btree" ("realm_id");



CREATE INDEX "idx_auth_exec_flow" ON "keycloak"."authentication_execution" USING "btree" ("flow_id");



CREATE INDEX "idx_auth_exec_realm_flow" ON "keycloak"."authentication_execution" USING "btree" ("realm_id", "flow_id");



CREATE INDEX "idx_auth_flow_realm" ON "keycloak"."authentication_flow" USING "btree" ("realm_id");



CREATE INDEX "idx_cl_clscope" ON "keycloak"."client_scope_client" USING "btree" ("scope_id");



CREATE INDEX "idx_client_att_by_name_value" ON "keycloak"."client_attributes" USING "btree" ("name", "substr"("value", 1, 255));



CREATE INDEX "idx_client_id" ON "keycloak"."client" USING "btree" ("client_id");



CREATE INDEX "idx_client_init_acc_realm" ON "keycloak"."client_initial_access" USING "btree" ("realm_id");



CREATE INDEX "idx_client_session_session" ON "keycloak"."client_session" USING "btree" ("session_id");



CREATE INDEX "idx_clscope_attrs" ON "keycloak"."client_scope_attributes" USING "btree" ("scope_id");



CREATE INDEX "idx_clscope_cl" ON "keycloak"."client_scope_client" USING "btree" ("client_id");



CREATE INDEX "idx_clscope_protmap" ON "keycloak"."protocol_mapper" USING "btree" ("client_scope_id");



CREATE INDEX "idx_clscope_role" ON "keycloak"."client_scope_role_mapping" USING "btree" ("scope_id");



CREATE INDEX "idx_compo_config_compo" ON "keycloak"."component_config" USING "btree" ("component_id");



CREATE INDEX "idx_component_provider_type" ON "keycloak"."component" USING "btree" ("provider_type");



CREATE INDEX "idx_component_realm" ON "keycloak"."component" USING "btree" ("realm_id");



CREATE INDEX "idx_composite" ON "keycloak"."composite_role" USING "btree" ("composite");



CREATE INDEX "idx_composite_child" ON "keycloak"."composite_role" USING "btree" ("child_role");



CREATE INDEX "idx_defcls_realm" ON "keycloak"."default_client_scope" USING "btree" ("realm_id");



CREATE INDEX "idx_defcls_scope" ON "keycloak"."default_client_scope" USING "btree" ("scope_id");



CREATE INDEX "idx_event_time" ON "keycloak"."event_entity" USING "btree" ("realm_id", "event_time");



CREATE INDEX "idx_fedidentity_feduser" ON "keycloak"."federated_identity" USING "btree" ("federated_user_id");



CREATE INDEX "idx_fedidentity_user" ON "keycloak"."federated_identity" USING "btree" ("user_id");



CREATE INDEX "idx_fu_attribute" ON "keycloak"."fed_user_attribute" USING "btree" ("user_id", "realm_id", "name");



CREATE INDEX "idx_fu_cnsnt_ext" ON "keycloak"."fed_user_consent" USING "btree" ("user_id", "client_storage_provider", "external_client_id");



CREATE INDEX "idx_fu_consent" ON "keycloak"."fed_user_consent" USING "btree" ("user_id", "client_id");



CREATE INDEX "idx_fu_consent_ru" ON "keycloak"."fed_user_consent" USING "btree" ("realm_id", "user_id");



CREATE INDEX "idx_fu_credential" ON "keycloak"."fed_user_credential" USING "btree" ("user_id", "type");



CREATE INDEX "idx_fu_credential_ru" ON "keycloak"."fed_user_credential" USING "btree" ("realm_id", "user_id");



CREATE INDEX "idx_fu_group_membership" ON "keycloak"."fed_user_group_membership" USING "btree" ("user_id", "group_id");



CREATE INDEX "idx_fu_group_membership_ru" ON "keycloak"."fed_user_group_membership" USING "btree" ("realm_id", "user_id");



CREATE INDEX "idx_fu_required_action" ON "keycloak"."fed_user_required_action" USING "btree" ("user_id", "required_action");



CREATE INDEX "idx_fu_required_action_ru" ON "keycloak"."fed_user_required_action" USING "btree" ("realm_id", "user_id");



CREATE INDEX "idx_fu_role_mapping" ON "keycloak"."fed_user_role_mapping" USING "btree" ("user_id", "role_id");



CREATE INDEX "idx_fu_role_mapping_ru" ON "keycloak"."fed_user_role_mapping" USING "btree" ("realm_id", "user_id");



CREATE INDEX "idx_group_att_by_name_value" ON "keycloak"."group_attribute" USING "btree" ("name", (("value")::character varying(250)));



CREATE INDEX "idx_group_attr_group" ON "keycloak"."group_attribute" USING "btree" ("group_id");



CREATE INDEX "idx_group_role_mapp_group" ON "keycloak"."group_role_mapping" USING "btree" ("group_id");



CREATE INDEX "idx_id_prov_mapp_realm" ON "keycloak"."identity_provider_mapper" USING "btree" ("realm_id");



CREATE INDEX "idx_ident_prov_realm" ON "keycloak"."identity_provider" USING "btree" ("realm_id");



CREATE INDEX "idx_keycloak_role_client" ON "keycloak"."keycloak_role" USING "btree" ("client");



CREATE INDEX "idx_keycloak_role_realm" ON "keycloak"."keycloak_role" USING "btree" ("realm");



CREATE INDEX "idx_offline_uss_by_broker_session_id" ON "keycloak"."offline_user_session" USING "btree" ("broker_session_id", "realm_id");



CREATE INDEX "idx_offline_uss_by_last_session_refresh" ON "keycloak"."offline_user_session" USING "btree" ("realm_id", "offline_flag", "last_session_refresh");



CREATE INDEX "idx_offline_uss_by_user" ON "keycloak"."offline_user_session" USING "btree" ("user_id", "realm_id", "offline_flag");



CREATE INDEX "idx_perm_ticket_owner" ON "keycloak"."resource_server_perm_ticket" USING "btree" ("owner");



CREATE INDEX "idx_perm_ticket_requester" ON "keycloak"."resource_server_perm_ticket" USING "btree" ("requester");



CREATE INDEX "idx_protocol_mapper_client" ON "keycloak"."protocol_mapper" USING "btree" ("client_id");



CREATE INDEX "idx_realm_attr_realm" ON "keycloak"."realm_attribute" USING "btree" ("realm_id");



CREATE INDEX "idx_realm_clscope" ON "keycloak"."client_scope" USING "btree" ("realm_id");



CREATE INDEX "idx_realm_def_grp_realm" ON "keycloak"."realm_default_groups" USING "btree" ("realm_id");



CREATE INDEX "idx_realm_evt_list_realm" ON "keycloak"."realm_events_listeners" USING "btree" ("realm_id");



CREATE INDEX "idx_realm_evt_types_realm" ON "keycloak"."realm_enabled_event_types" USING "btree" ("realm_id");



CREATE INDEX "idx_realm_master_adm_cli" ON "keycloak"."realm" USING "btree" ("master_admin_client");



CREATE INDEX "idx_realm_supp_local_realm" ON "keycloak"."realm_supported_locales" USING "btree" ("realm_id");



CREATE INDEX "idx_redir_uri_client" ON "keycloak"."redirect_uris" USING "btree" ("client_id");



CREATE INDEX "idx_req_act_prov_realm" ON "keycloak"."required_action_provider" USING "btree" ("realm_id");



CREATE INDEX "idx_res_policy_policy" ON "keycloak"."resource_policy" USING "btree" ("policy_id");



CREATE INDEX "idx_res_scope_scope" ON "keycloak"."resource_scope" USING "btree" ("scope_id");



CREATE INDEX "idx_res_serv_pol_res_serv" ON "keycloak"."resource_server_policy" USING "btree" ("resource_server_id");



CREATE INDEX "idx_res_srv_res_res_srv" ON "keycloak"."resource_server_resource" USING "btree" ("resource_server_id");



CREATE INDEX "idx_res_srv_scope_res_srv" ON "keycloak"."resource_server_scope" USING "btree" ("resource_server_id");



CREATE INDEX "idx_role_attribute" ON "keycloak"."role_attribute" USING "btree" ("role_id");



CREATE INDEX "idx_role_clscope" ON "keycloak"."client_scope_role_mapping" USING "btree" ("role_id");



CREATE INDEX "idx_scope_mapping_role" ON "keycloak"."scope_mapping" USING "btree" ("role_id");



CREATE INDEX "idx_scope_policy_policy" ON "keycloak"."scope_policy" USING "btree" ("policy_id");



CREATE INDEX "idx_update_time" ON "keycloak"."migration_model" USING "btree" ("update_time");



CREATE INDEX "idx_us_sess_id_on_cl_sess" ON "keycloak"."offline_client_session" USING "btree" ("user_session_id");



CREATE INDEX "idx_usconsent_clscope" ON "keycloak"."user_consent_client_scope" USING "btree" ("user_consent_id");



CREATE INDEX "idx_usconsent_scope_id" ON "keycloak"."user_consent_client_scope" USING "btree" ("scope_id");



CREATE INDEX "idx_user_attribute" ON "keycloak"."user_attribute" USING "btree" ("user_id");



CREATE INDEX "idx_user_attribute_name" ON "keycloak"."user_attribute" USING "btree" ("name", "value");



CREATE INDEX "idx_user_consent" ON "keycloak"."user_consent" USING "btree" ("user_id");



CREATE INDEX "idx_user_credential" ON "keycloak"."credential" USING "btree" ("user_id");



CREATE INDEX "idx_user_email" ON "keycloak"."user_entity" USING "btree" ("email");



CREATE INDEX "idx_user_group_mapping" ON "keycloak"."user_group_membership" USING "btree" ("user_id");



CREATE INDEX "idx_user_reqactions" ON "keycloak"."user_required_action" USING "btree" ("user_id");



CREATE INDEX "idx_user_role_mapping" ON "keycloak"."user_role_mapping" USING "btree" ("user_id");



CREATE INDEX "idx_user_service_account" ON "keycloak"."user_entity" USING "btree" ("realm_id", "service_account_client_link");



CREATE INDEX "idx_usr_fed_map_fed_prv" ON "keycloak"."user_federation_mapper" USING "btree" ("federation_provider_id");



CREATE INDEX "idx_usr_fed_map_realm" ON "keycloak"."user_federation_mapper" USING "btree" ("realm_id");



CREATE INDEX "idx_usr_fed_prv_realm" ON "keycloak"."user_federation_provider" USING "btree" ("realm_id");



CREATE INDEX "idx_web_orig_client" ON "keycloak"."web_origins" USING "btree" ("client_id");



CREATE INDEX "user_attr_long_values" ON "keycloak"."user_attribute" USING "btree" ("long_value_hash", "name");



CREATE INDEX "user_attr_long_values_lower_case" ON "keycloak"."user_attribute" USING "btree" ("long_value_hash_lower_case", "name");



CREATE INDEX "article_title_trgm_idx" ON "public"."publications" USING "gin" ("article_title" "public"."gin_trgm_ops");



CREATE INDEX "doc_groups_enabled_course_name_idx" ON "public"."doc_groups" USING "btree" ("enabled", "course_name");



CREATE INDEX "documents_course_name_idx" ON "public"."documents" USING "hash" ("course_name");



CREATE INDEX "documents_created_at_idx" ON "public"."documents" USING "btree" ("created_at");



CREATE INDEX "documents_doc_groups_doc_group_id_idx" ON "public"."documents_doc_groups" USING "btree" ("doc_group_id");



CREATE INDEX "documents_doc_groups_document_id_idx" ON "public"."documents_doc_groups" USING "btree" ("document_id");



CREATE INDEX "documents_in_progress_course_name_idx" ON "public"."documents_in_progress" USING "btree" ("course_name");



CREATE INDEX "idx_article_title" ON "public"."publications" USING "btree" ("article_title");



CREATE INDEX "idx_conversation_id" ON "public"."messages" USING "btree" ("conversation_id");



CREATE INDEX "idx_doc_s3_path" ON "public"."documents" USING "btree" ("s3_path");



CREATE INDEX "idx_publications_pmid" ON "public"."publications" USING "btree" ("pmid");



CREATE INDEX "idx_user_email_folders" ON "public"."folders" USING "btree" ("user_email");



CREATE INDEX "idx_user_email_updated_at" ON "public"."conversations" USING "btree" ("user_email", "updated_at" DESC);



CREATE INDEX "llm-convo-monitor_course_name_idx" ON "public"."llm-convo-monitor" USING "hash" ("course_name");



CREATE INDEX "publications_pmcid_doi_idx" ON "public"."publications" USING "btree" ("pmcid", "doi");



CREATE INDEX "publications_pmcid_idx" ON "public"."publications" USING "btree" ("pmcid");



CREATE OR REPLACE TRIGGER "after_project_insert" AFTER INSERT ON "public"."projects" FOR EACH ROW EXECUTE FUNCTION "public"."initialize_project_stats"();



CREATE OR REPLACE TRIGGER "project_stats_trigger" AFTER INSERT OR DELETE OR UPDATE ON "public"."llm-convo-monitor" FOR EACH ROW EXECUTE FUNCTION "public"."update_project_stats"();



CREATE OR REPLACE TRIGGER "trg_update_doc_count_after_insert" AFTER INSERT OR DELETE ON "public"."documents_doc_groups" FOR EACH ROW EXECUTE FUNCTION "public"."update_doc_count"();



ALTER TABLE ONLY "keycloak"."client_session_auth_status"
    ADD CONSTRAINT "auth_status_constraint" FOREIGN KEY ("client_session") REFERENCES "keycloak"."client_session"("id");



ALTER TABLE ONLY "keycloak"."identity_provider"
    ADD CONSTRAINT "fk2b4ebc52ae5c3b34" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."client_attributes"
    ADD CONSTRAINT "fk3c47c64beacca966" FOREIGN KEY ("client_id") REFERENCES "keycloak"."client"("id");



ALTER TABLE ONLY "keycloak"."federated_identity"
    ADD CONSTRAINT "fk404288b92ef007a6" FOREIGN KEY ("user_id") REFERENCES "keycloak"."user_entity"("id");



ALTER TABLE ONLY "keycloak"."client_node_registrations"
    ADD CONSTRAINT "fk4129723ba992f594" FOREIGN KEY ("client_id") REFERENCES "keycloak"."client"("id");



ALTER TABLE ONLY "keycloak"."client_session_note"
    ADD CONSTRAINT "fk5edfb00ff51c2736" FOREIGN KEY ("client_session") REFERENCES "keycloak"."client_session"("id");



ALTER TABLE ONLY "keycloak"."user_session_note"
    ADD CONSTRAINT "fk5edfb00ff51d3472" FOREIGN KEY ("user_session") REFERENCES "keycloak"."user_session"("id");



ALTER TABLE ONLY "keycloak"."client_session_role"
    ADD CONSTRAINT "fk_11b7sgqw18i532811v7o2dv76" FOREIGN KEY ("client_session") REFERENCES "keycloak"."client_session"("id");



ALTER TABLE ONLY "keycloak"."redirect_uris"
    ADD CONSTRAINT "fk_1burs8pb4ouj97h5wuppahv9f" FOREIGN KEY ("client_id") REFERENCES "keycloak"."client"("id");



ALTER TABLE ONLY "keycloak"."user_federation_provider"
    ADD CONSTRAINT "fk_1fj32f6ptolw2qy60cd8n01e8" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."client_session_prot_mapper"
    ADD CONSTRAINT "fk_33a8sgqw18i532811v7o2dk89" FOREIGN KEY ("client_session") REFERENCES "keycloak"."client_session"("id");



ALTER TABLE ONLY "keycloak"."realm_required_credential"
    ADD CONSTRAINT "fk_5hg65lybevavkqfki3kponh9v" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."resource_attribute"
    ADD CONSTRAINT "fk_5hrm2vlf9ql5fu022kqepovbr" FOREIGN KEY ("resource_id") REFERENCES "keycloak"."resource_server_resource"("id");



ALTER TABLE ONLY "keycloak"."user_attribute"
    ADD CONSTRAINT "fk_5hrm2vlf9ql5fu043kqepovbr" FOREIGN KEY ("user_id") REFERENCES "keycloak"."user_entity"("id");



ALTER TABLE ONLY "keycloak"."user_required_action"
    ADD CONSTRAINT "fk_6qj3w1jw9cvafhe19bwsiuvmd" FOREIGN KEY ("user_id") REFERENCES "keycloak"."user_entity"("id");



ALTER TABLE ONLY "keycloak"."keycloak_role"
    ADD CONSTRAINT "fk_6vyqfe4cn4wlq8r6kt5vdsj5c" FOREIGN KEY ("realm") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."realm_smtp_config"
    ADD CONSTRAINT "fk_70ej8xdxgxd0b9hh6180irr0o" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."realm_attribute"
    ADD CONSTRAINT "fk_8shxd6l3e9atqukacxgpffptw" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."composite_role"
    ADD CONSTRAINT "fk_a63wvekftu8jo1pnj81e7mce2" FOREIGN KEY ("composite") REFERENCES "keycloak"."keycloak_role"("id");



ALTER TABLE ONLY "keycloak"."authentication_execution"
    ADD CONSTRAINT "fk_auth_exec_flow" FOREIGN KEY ("flow_id") REFERENCES "keycloak"."authentication_flow"("id");



ALTER TABLE ONLY "keycloak"."authentication_execution"
    ADD CONSTRAINT "fk_auth_exec_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."authentication_flow"
    ADD CONSTRAINT "fk_auth_flow_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."authenticator_config"
    ADD CONSTRAINT "fk_auth_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."client_session"
    ADD CONSTRAINT "fk_b4ao2vcvat6ukau74wbwtfqo1" FOREIGN KEY ("session_id") REFERENCES "keycloak"."user_session"("id");



ALTER TABLE ONLY "keycloak"."user_role_mapping"
    ADD CONSTRAINT "fk_c4fqv34p1mbylloxang7b1q3l" FOREIGN KEY ("user_id") REFERENCES "keycloak"."user_entity"("id");



ALTER TABLE ONLY "keycloak"."client_scope_attributes"
    ADD CONSTRAINT "fk_cl_scope_attr_scope" FOREIGN KEY ("scope_id") REFERENCES "keycloak"."client_scope"("id");



ALTER TABLE ONLY "keycloak"."client_scope_role_mapping"
    ADD CONSTRAINT "fk_cl_scope_rm_scope" FOREIGN KEY ("scope_id") REFERENCES "keycloak"."client_scope"("id");



ALTER TABLE ONLY "keycloak"."client_user_session_note"
    ADD CONSTRAINT "fk_cl_usr_ses_note" FOREIGN KEY ("client_session") REFERENCES "keycloak"."client_session"("id");



ALTER TABLE ONLY "keycloak"."protocol_mapper"
    ADD CONSTRAINT "fk_cli_scope_mapper" FOREIGN KEY ("client_scope_id") REFERENCES "keycloak"."client_scope"("id");



ALTER TABLE ONLY "keycloak"."client_initial_access"
    ADD CONSTRAINT "fk_client_init_acc_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."component_config"
    ADD CONSTRAINT "fk_component_config" FOREIGN KEY ("component_id") REFERENCES "keycloak"."component"("id");



ALTER TABLE ONLY "keycloak"."component"
    ADD CONSTRAINT "fk_component_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."realm_default_groups"
    ADD CONSTRAINT "fk_def_groups_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."user_federation_mapper_config"
    ADD CONSTRAINT "fk_fedmapper_cfg" FOREIGN KEY ("user_federation_mapper_id") REFERENCES "keycloak"."user_federation_mapper"("id");



ALTER TABLE ONLY "keycloak"."user_federation_mapper"
    ADD CONSTRAINT "fk_fedmapperpm_fedprv" FOREIGN KEY ("federation_provider_id") REFERENCES "keycloak"."user_federation_provider"("id");



ALTER TABLE ONLY "keycloak"."user_federation_mapper"
    ADD CONSTRAINT "fk_fedmapperpm_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."associated_policy"
    ADD CONSTRAINT "fk_frsr5s213xcx4wnkog82ssrfy" FOREIGN KEY ("associated_policy_id") REFERENCES "keycloak"."resource_server_policy"("id");



ALTER TABLE ONLY "keycloak"."scope_policy"
    ADD CONSTRAINT "fk_frsrasp13xcx4wnkog82ssrfy" FOREIGN KEY ("policy_id") REFERENCES "keycloak"."resource_server_policy"("id");



ALTER TABLE ONLY "keycloak"."resource_server_perm_ticket"
    ADD CONSTRAINT "fk_frsrho213xcx4wnkog82sspmt" FOREIGN KEY ("resource_server_id") REFERENCES "keycloak"."resource_server"("id");



ALTER TABLE ONLY "keycloak"."resource_server_resource"
    ADD CONSTRAINT "fk_frsrho213xcx4wnkog82ssrfy" FOREIGN KEY ("resource_server_id") REFERENCES "keycloak"."resource_server"("id");



ALTER TABLE ONLY "keycloak"."resource_server_perm_ticket"
    ADD CONSTRAINT "fk_frsrho213xcx4wnkog83sspmt" FOREIGN KEY ("resource_id") REFERENCES "keycloak"."resource_server_resource"("id");



ALTER TABLE ONLY "keycloak"."resource_server_perm_ticket"
    ADD CONSTRAINT "fk_frsrho213xcx4wnkog84sspmt" FOREIGN KEY ("scope_id") REFERENCES "keycloak"."resource_server_scope"("id");



ALTER TABLE ONLY "keycloak"."associated_policy"
    ADD CONSTRAINT "fk_frsrpas14xcx4wnkog82ssrfy" FOREIGN KEY ("policy_id") REFERENCES "keycloak"."resource_server_policy"("id");



ALTER TABLE ONLY "keycloak"."scope_policy"
    ADD CONSTRAINT "fk_frsrpass3xcx4wnkog82ssrfy" FOREIGN KEY ("scope_id") REFERENCES "keycloak"."resource_server_scope"("id");



ALTER TABLE ONLY "keycloak"."resource_server_perm_ticket"
    ADD CONSTRAINT "fk_frsrpo2128cx4wnkog82ssrfy" FOREIGN KEY ("policy_id") REFERENCES "keycloak"."resource_server_policy"("id");



ALTER TABLE ONLY "keycloak"."resource_server_policy"
    ADD CONSTRAINT "fk_frsrpo213xcx4wnkog82ssrfy" FOREIGN KEY ("resource_server_id") REFERENCES "keycloak"."resource_server"("id");



ALTER TABLE ONLY "keycloak"."resource_scope"
    ADD CONSTRAINT "fk_frsrpos13xcx4wnkog82ssrfy" FOREIGN KEY ("resource_id") REFERENCES "keycloak"."resource_server_resource"("id");



ALTER TABLE ONLY "keycloak"."resource_policy"
    ADD CONSTRAINT "fk_frsrpos53xcx4wnkog82ssrfy" FOREIGN KEY ("resource_id") REFERENCES "keycloak"."resource_server_resource"("id");



ALTER TABLE ONLY "keycloak"."resource_policy"
    ADD CONSTRAINT "fk_frsrpp213xcx4wnkog82ssrfy" FOREIGN KEY ("policy_id") REFERENCES "keycloak"."resource_server_policy"("id");



ALTER TABLE ONLY "keycloak"."resource_scope"
    ADD CONSTRAINT "fk_frsrps213xcx4wnkog82ssrfy" FOREIGN KEY ("scope_id") REFERENCES "keycloak"."resource_server_scope"("id");



ALTER TABLE ONLY "keycloak"."resource_server_scope"
    ADD CONSTRAINT "fk_frsrso213xcx4wnkog82ssrfy" FOREIGN KEY ("resource_server_id") REFERENCES "keycloak"."resource_server"("id");



ALTER TABLE ONLY "keycloak"."composite_role"
    ADD CONSTRAINT "fk_gr7thllb9lu8q4vqa4524jjy8" FOREIGN KEY ("child_role") REFERENCES "keycloak"."keycloak_role"("id");



ALTER TABLE ONLY "keycloak"."user_consent_client_scope"
    ADD CONSTRAINT "fk_grntcsnt_clsc_usc" FOREIGN KEY ("user_consent_id") REFERENCES "keycloak"."user_consent"("id");



ALTER TABLE ONLY "keycloak"."user_consent"
    ADD CONSTRAINT "fk_grntcsnt_user" FOREIGN KEY ("user_id") REFERENCES "keycloak"."user_entity"("id");



ALTER TABLE ONLY "keycloak"."group_attribute"
    ADD CONSTRAINT "fk_group_attribute_group" FOREIGN KEY ("group_id") REFERENCES "keycloak"."keycloak_group"("id");



ALTER TABLE ONLY "keycloak"."group_role_mapping"
    ADD CONSTRAINT "fk_group_role_group" FOREIGN KEY ("group_id") REFERENCES "keycloak"."keycloak_group"("id");



ALTER TABLE ONLY "keycloak"."realm_enabled_event_types"
    ADD CONSTRAINT "fk_h846o4h0w8epx5nwedrf5y69j" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."realm_events_listeners"
    ADD CONSTRAINT "fk_h846o4h0w8epx5nxev9f5y69j" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."identity_provider_mapper"
    ADD CONSTRAINT "fk_idpm_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."idp_mapper_config"
    ADD CONSTRAINT "fk_idpmconfig" FOREIGN KEY ("idp_mapper_id") REFERENCES "keycloak"."identity_provider_mapper"("id");



ALTER TABLE ONLY "keycloak"."web_origins"
    ADD CONSTRAINT "fk_lojpho213xcx4wnkog82ssrfy" FOREIGN KEY ("client_id") REFERENCES "keycloak"."client"("id");



ALTER TABLE ONLY "keycloak"."scope_mapping"
    ADD CONSTRAINT "fk_ouse064plmlr732lxjcn1q5f1" FOREIGN KEY ("client_id") REFERENCES "keycloak"."client"("id");



ALTER TABLE ONLY "keycloak"."protocol_mapper"
    ADD CONSTRAINT "fk_pcm_realm" FOREIGN KEY ("client_id") REFERENCES "keycloak"."client"("id");



ALTER TABLE ONLY "keycloak"."credential"
    ADD CONSTRAINT "fk_pfyr0glasqyl0dei3kl69r6v0" FOREIGN KEY ("user_id") REFERENCES "keycloak"."user_entity"("id");



ALTER TABLE ONLY "keycloak"."protocol_mapper_config"
    ADD CONSTRAINT "fk_pmconfig" FOREIGN KEY ("protocol_mapper_id") REFERENCES "keycloak"."protocol_mapper"("id");



ALTER TABLE ONLY "keycloak"."default_client_scope"
    ADD CONSTRAINT "fk_r_def_cli_scope_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."required_action_provider"
    ADD CONSTRAINT "fk_req_act_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."resource_uris"
    ADD CONSTRAINT "fk_resource_server_uris" FOREIGN KEY ("resource_id") REFERENCES "keycloak"."resource_server_resource"("id");



ALTER TABLE ONLY "keycloak"."role_attribute"
    ADD CONSTRAINT "fk_role_attribute_id" FOREIGN KEY ("role_id") REFERENCES "keycloak"."keycloak_role"("id");



ALTER TABLE ONLY "keycloak"."realm_supported_locales"
    ADD CONSTRAINT "fk_supported_locales_realm" FOREIGN KEY ("realm_id") REFERENCES "keycloak"."realm"("id");



ALTER TABLE ONLY "keycloak"."user_federation_config"
    ADD CONSTRAINT "fk_t13hpu1j94r2ebpekr39x5eu5" FOREIGN KEY ("user_federation_provider_id") REFERENCES "keycloak"."user_federation_provider"("id");



ALTER TABLE ONLY "keycloak"."user_group_membership"
    ADD CONSTRAINT "fk_user_group_user" FOREIGN KEY ("user_id") REFERENCES "keycloak"."user_entity"("id");



ALTER TABLE ONLY "keycloak"."policy_config"
    ADD CONSTRAINT "fkdc34197cf864c4e43" FOREIGN KEY ("policy_id") REFERENCES "keycloak"."resource_server_policy"("id");



ALTER TABLE ONLY "keycloak"."identity_provider_config"
    ADD CONSTRAINT "fkdc4897cf864c4e43" FOREIGN KEY ("identity_provider_id") REFERENCES "keycloak"."identity_provider"("internal_id");



ALTER TABLE ONLY "public"."cedar_chunks"
    ADD CONSTRAINT "cedar_chunks_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."cedar_documents"("id");



ALTER TABLE ONLY "public"."cedar_document_metadata"
    ADD CONSTRAINT "cedar_document_metadata_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."cedar_documents"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."cedar_runs"
    ADD CONSTRAINT "cedar_runs_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."cedar_documents"("id");



ALTER TABLE ONLY "public"."conversations"
    ADD CONSTRAINT "conversations_folder_id_fkey" FOREIGN KEY ("folder_id") REFERENCES "public"."folders"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."doc_groups_sharing"
    ADD CONSTRAINT "doc_groups_sharing_destination_project_id_fkey" FOREIGN KEY ("destination_project_id") REFERENCES "public"."projects"("id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."doc_groups_sharing"
    ADD CONSTRAINT "doc_groups_sharing_destination_project_name_fkey" FOREIGN KEY ("destination_project_name") REFERENCES "public"."projects"("course_name") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."doc_groups_sharing"
    ADD CONSTRAINT "doc_groups_sharing_doc_group_id_fkey" FOREIGN KEY ("doc_group_id") REFERENCES "public"."doc_groups"("id") ON UPDATE CASCADE ON DELETE CASCADE;



ALTER TABLE ONLY "public"."llm-guided-contexts"
    ADD CONSTRAINT "llm-guided-contexts_doc_id_fkey" FOREIGN KEY ("doc_id") REFERENCES "public"."llm-guided-docs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."llm-guided-contexts"
    ADD CONSTRAINT "llm-guided-contexts_section_id_fkey" FOREIGN KEY ("section_id") REFERENCES "public"."llm-guided-sections"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."llm-guided-sections"
    ADD CONSTRAINT "llm-guided-sections_doc_id_fkey" FOREIGN KEY ("doc_id") REFERENCES "public"."llm-guided-docs"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "public"."conversations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."projects"
    ADD CONSTRAINT "projects_subscribed_fkey" FOREIGN KEY ("subscribed") REFERENCES "public"."doc_groups"("id") ON UPDATE CASCADE ON DELETE SET NULL;



ALTER TABLE ONLY "public"."documents_doc_groups"
    ADD CONSTRAINT "public_documents_doc_groups_doc_group_id_fkey" FOREIGN KEY ("doc_group_id") REFERENCES "public"."doc_groups"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."documents_doc_groups"
    ADD CONSTRAINT "public_documents_doc_groups_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."documents"("id") ON DELETE CASCADE;



CREATE POLICY "Enable execute for anon/service_role users only" ON "public"."api_keys" TO "anon", "service_role";



ALTER TABLE "public"."api_keys" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cedar_runs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."conversations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cropwizard-papers" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."depricated_uiuc_chatbot" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."doc_groups" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."doc_groups_sharing" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."documents" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."documents_doc_groups" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."documents_failed" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."documents_in_progress" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."email-newsletter" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."folders" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."llm-convo-monitor" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."llm-guided-contexts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."llm-guided-docs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."llm-guided-sections" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."messages" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."n8n_workflows" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."nal_publications" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."pre_authorized_api_keys" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."project_stats" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."projects" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."publications" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."pubmed_daily_update" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."uiuc-course-table" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."usage_metrics" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."project_stats";



REVOKE USAGE ON SCHEMA "public" FROM PUBLIC;
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";
GRANT USAGE ON SCHEMA "public" TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_in"("cstring") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_in"("cstring") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_in"("cstring") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_in"("cstring") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_out"("public"."gtrgm") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_out"("public"."gtrgm") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_out"("public"."gtrgm") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_out"("public"."gtrgm") TO "postgres";













































































































































































































































GRANT ALL ON FUNCTION "public"."add_document_to_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "anon";
GRANT ALL ON FUNCTION "public"."add_document_to_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "authenticated";
GRANT ALL ON FUNCTION "public"."add_document_to_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "service_role";



GRANT ALL ON FUNCTION "public"."add_document_to_group_url"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "anon";
GRANT ALL ON FUNCTION "public"."add_document_to_group_url"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "authenticated";
GRANT ALL ON FUNCTION "public"."add_document_to_group_url"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_readable_filename" "text", "p_doc_groups" "text"[]) TO "service_role";



GRANT ALL ON FUNCTION "public"."c"() TO "anon";
GRANT ALL ON FUNCTION "public"."c"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."c"() TO "service_role";



GRANT ALL ON FUNCTION "public"."calculate_weekly_trends"("course_name_input" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."calculate_weekly_trends"("course_name_input" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."calculate_weekly_trends"("course_name_input" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."check_and_lock_flows_v2"("id" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."check_and_lock_flows_v2"("id" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."check_and_lock_flows_v2"("id" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."cn"() TO "anon";
GRANT ALL ON FUNCTION "public"."cn"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."cn"() TO "service_role";



GRANT ALL ON FUNCTION "public"."count_models_by_project"("project_name_input" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."count_models_by_project"("project_name_input" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."count_models_by_project"("project_name_input" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."get_base_url_with_doc_groups"("p_course_name" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."get_base_url_with_doc_groups"("p_course_name" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_base_url_with_doc_groups"("p_course_name" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."get_convo_maps"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_convo_maps"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_convo_maps"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_course_details"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_course_details"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_course_details"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_course_names"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_course_names"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_course_names"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_distinct_base_urls"("p_course_name" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."get_distinct_base_urls"("p_course_name" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_distinct_base_urls"("p_course_name" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."get_distinct_course_names"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_distinct_course_names"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_distinct_course_names"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_doc_map_details"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_doc_map_details"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_doc_map_details"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_latest_workflow_id"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_latest_workflow_id"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_latest_workflow_id"() TO "service_role";



GRANT ALL ON FUNCTION "public"."get_run_data"("p_run_ids" "text", "p_limit" integer, "p_offset" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."get_run_data"("p_run_ids" "text", "p_limit" integer, "p_offset" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_run_data"("p_run_ids" "text", "p_limit" integer, "p_offset" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."gin_extract_query_trgm"("text", "internal", smallint, "internal", "internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gin_extract_query_trgm"("text", "internal", smallint, "internal", "internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gin_extract_query_trgm"("text", "internal", smallint, "internal", "internal", "internal", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gin_extract_query_trgm"("text", "internal", smallint, "internal", "internal", "internal", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gin_extract_value_trgm"("text", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gin_extract_value_trgm"("text", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gin_extract_value_trgm"("text", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gin_extract_value_trgm"("text", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gin_trgm_consistent"("internal", smallint, "text", integer, "internal", "internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gin_trgm_consistent"("internal", smallint, "text", integer, "internal", "internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gin_trgm_consistent"("internal", smallint, "text", integer, "internal", "internal", "internal", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gin_trgm_consistent"("internal", smallint, "text", integer, "internal", "internal", "internal", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gin_trgm_triconsistent"("internal", smallint, "text", integer, "internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gin_trgm_triconsistent"("internal", smallint, "text", integer, "internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gin_trgm_triconsistent"("internal", smallint, "text", integer, "internal", "internal", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gin_trgm_triconsistent"("internal", smallint, "text", integer, "internal", "internal", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_compress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_compress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_compress"("internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_compress"("internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_consistent"("internal", "text", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_consistent"("internal", "text", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_consistent"("internal", "text", smallint, "oid", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_consistent"("internal", "text", smallint, "oid", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_decompress"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_decompress"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_decompress"("internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_decompress"("internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_distance"("internal", "text", smallint, "oid", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_distance"("internal", "text", smallint, "oid", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_distance"("internal", "text", smallint, "oid", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_distance"("internal", "text", smallint, "oid", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_options"("internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_options"("internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_options"("internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_options"("internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_penalty"("internal", "internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_penalty"("internal", "internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_penalty"("internal", "internal", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_penalty"("internal", "internal", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_picksplit"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_picksplit"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_picksplit"("internal", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_picksplit"("internal", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_same"("public"."gtrgm", "public"."gtrgm", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_same"("public"."gtrgm", "public"."gtrgm", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_same"("public"."gtrgm", "public"."gtrgm", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_same"("public"."gtrgm", "public"."gtrgm", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."gtrgm_union"("internal", "internal") TO "anon";
GRANT ALL ON FUNCTION "public"."gtrgm_union"("internal", "internal") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gtrgm_union"("internal", "internal") TO "service_role";
GRANT ALL ON FUNCTION "public"."gtrgm_union"("internal", "internal") TO "postgres";



GRANT ALL ON FUNCTION "public"."hello"() TO "anon";
GRANT ALL ON FUNCTION "public"."hello"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."hello"() TO "service_role";



GRANT ALL ON FUNCTION "public"."hypopg"(OUT "indexname" "text", OUT "indexrelid" "oid", OUT "indrelid" "oid", OUT "innatts" integer, OUT "indisunique" boolean, OUT "indkey" "int2vector", OUT "indcollation" "oidvector", OUT "indclass" "oidvector", OUT "indoption" "oidvector", OUT "indexprs" "pg_node_tree", OUT "indpred" "pg_node_tree", OUT "amid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg"(OUT "indexname" "text", OUT "indexrelid" "oid", OUT "indrelid" "oid", OUT "innatts" integer, OUT "indisunique" boolean, OUT "indkey" "int2vector", OUT "indcollation" "oidvector", OUT "indclass" "oidvector", OUT "indoption" "oidvector", OUT "indexprs" "pg_node_tree", OUT "indpred" "pg_node_tree", OUT "amid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg"(OUT "indexname" "text", OUT "indexrelid" "oid", OUT "indrelid" "oid", OUT "innatts" integer, OUT "indisunique" boolean, OUT "indkey" "int2vector", OUT "indcollation" "oidvector", OUT "indclass" "oidvector", OUT "indoption" "oidvector", OUT "indexprs" "pg_node_tree", OUT "indpred" "pg_node_tree", OUT "amid" "oid") TO "service_role";
GRANT ALL ON FUNCTION "public"."hypopg"(OUT "indexname" "text", OUT "indexrelid" "oid", OUT "indrelid" "oid", OUT "innatts" integer, OUT "indisunique" boolean, OUT "indkey" "int2vector", OUT "indcollation" "oidvector", OUT "indclass" "oidvector", OUT "indoption" "oidvector", OUT "indexprs" "pg_node_tree", OUT "indpred" "pg_node_tree", OUT "amid" "oid") TO "postgres";



GRANT ALL ON FUNCTION "public"."hypopg_create_index"("sql_order" "text", OUT "indexrelid" "oid", OUT "indexname" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_create_index"("sql_order" "text", OUT "indexrelid" "oid", OUT "indexname" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_create_index"("sql_order" "text", OUT "indexrelid" "oid", OUT "indexname" "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."hypopg_create_index"("sql_order" "text", OUT "indexrelid" "oid", OUT "indexname" "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."hypopg_drop_index"("indexid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_drop_index"("indexid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_drop_index"("indexid" "oid") TO "service_role";
GRANT ALL ON FUNCTION "public"."hypopg_drop_index"("indexid" "oid") TO "postgres";



GRANT ALL ON FUNCTION "public"."hypopg_get_indexdef"("indexid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_get_indexdef"("indexid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_get_indexdef"("indexid" "oid") TO "service_role";
GRANT ALL ON FUNCTION "public"."hypopg_get_indexdef"("indexid" "oid") TO "postgres";



GRANT ALL ON FUNCTION "public"."hypopg_hidden_indexes"() TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_hidden_indexes"() TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_hidden_indexes"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_hidden_indexes"() TO "service_role";



GRANT ALL ON FUNCTION "public"."hypopg_hide_index"("indexid" "oid") TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_hide_index"("indexid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_hide_index"("indexid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_hide_index"("indexid" "oid") TO "service_role";



GRANT ALL ON FUNCTION "public"."hypopg_relation_size"("indexid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_relation_size"("indexid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_relation_size"("indexid" "oid") TO "service_role";
GRANT ALL ON FUNCTION "public"."hypopg_relation_size"("indexid" "oid") TO "postgres";



GRANT ALL ON FUNCTION "public"."hypopg_reset"() TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_reset"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_reset"() TO "service_role";
GRANT ALL ON FUNCTION "public"."hypopg_reset"() TO "postgres";



GRANT ALL ON FUNCTION "public"."hypopg_reset_index"() TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_reset_index"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_reset_index"() TO "service_role";
GRANT ALL ON FUNCTION "public"."hypopg_reset_index"() TO "postgres";



GRANT ALL ON FUNCTION "public"."hypopg_unhide_all_indexes"() TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_unhide_all_indexes"() TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_unhide_all_indexes"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_unhide_all_indexes"() TO "service_role";



GRANT ALL ON FUNCTION "public"."hypopg_unhide_index"("indexid" "oid") TO "postgres";
GRANT ALL ON FUNCTION "public"."hypopg_unhide_index"("indexid" "oid") TO "anon";
GRANT ALL ON FUNCTION "public"."hypopg_unhide_index"("indexid" "oid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."hypopg_unhide_index"("indexid" "oid") TO "service_role";



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



GRANT ALL ON FUNCTION "public"."index_advisor"("query" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."index_advisor"("query" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."index_advisor"("query" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."initialize_project_stats"() TO "anon";
GRANT ALL ON FUNCTION "public"."initialize_project_stats"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."initialize_project_stats"() TO "service_role";



GRANT ALL ON FUNCTION "public"."myfunc"() TO "anon";
GRANT ALL ON FUNCTION "public"."myfunc"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."myfunc"() TO "service_role";



GRANT ALL ON FUNCTION "public"."remove_document_from_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_doc_group" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."remove_document_from_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_doc_group" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."remove_document_from_group"("p_course_name" "text", "p_s3_path" "text", "p_url" "text", "p_doc_group" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."search_conversations"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_conversations"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_conversations"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."search_conversations_v2"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_conversations_v2"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_conversations_v2"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."search_conversations_v3"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."search_conversations_v3"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."search_conversations_v3"("p_user_email" "text", "p_project_name" "text", "p_search_term" "text", "p_limit" integer, "p_offset" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."set_limit"(real) TO "anon";
GRANT ALL ON FUNCTION "public"."set_limit"(real) TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_limit"(real) TO "service_role";
GRANT ALL ON FUNCTION "public"."set_limit"(real) TO "postgres";



GRANT ALL ON FUNCTION "public"."show_limit"() TO "anon";
GRANT ALL ON FUNCTION "public"."show_limit"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."show_limit"() TO "service_role";
GRANT ALL ON FUNCTION "public"."show_limit"() TO "postgres";



GRANT ALL ON FUNCTION "public"."show_trgm"("text") TO "anon";
GRANT ALL ON FUNCTION "public"."show_trgm"("text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."show_trgm"("text") TO "service_role";
GRANT ALL ON FUNCTION "public"."show_trgm"("text") TO "postgres";



GRANT ALL ON FUNCTION "public"."similarity"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."similarity"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."similarity"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."similarity"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."similarity_dist"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."similarity_dist"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."similarity_dist"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."similarity_dist"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."similarity_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."similarity_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."similarity_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."similarity_op"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."strict_word_similarity"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."strict_word_similarity"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."strict_word_similarity_commutator_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_commutator_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_commutator_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_commutator_op"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_commutator_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_commutator_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_commutator_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_commutator_op"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_dist_op"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."strict_word_similarity_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."strict_word_similarity_op"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."test_function"("id" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."test_function"("id" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."test_function"("id" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."update_doc_count"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_doc_count"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_doc_count"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_project_stats"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_project_stats"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_project_stats"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_total_messages_by_id_range"("start_id" integer, "end_id" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."update_total_messages_by_id_range"("start_id" integer, "end_id" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_total_messages_by_id_range"("start_id" integer, "end_id" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."word_similarity"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."word_similarity"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."word_similarity_commutator_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity_commutator_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity_commutator_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."word_similarity_commutator_op"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."word_similarity_dist_commutator_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_commutator_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_commutator_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_commutator_op"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."word_similarity_dist_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."word_similarity_dist_op"("text", "text") TO "postgres";



GRANT ALL ON FUNCTION "public"."word_similarity_op"("text", "text") TO "anon";
GRANT ALL ON FUNCTION "public"."word_similarity_op"("text", "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."word_similarity_op"("text", "text") TO "service_role";
GRANT ALL ON FUNCTION "public"."word_similarity_op"("text", "text") TO "postgres";


















GRANT ALL ON TABLE "public"."api_keys" TO "anon";
GRANT ALL ON TABLE "public"."api_keys" TO "authenticated";
GRANT ALL ON TABLE "public"."api_keys" TO "service_role";



GRANT ALL ON TABLE "public"."cedar_chunks" TO "anon";
GRANT ALL ON TABLE "public"."cedar_chunks" TO "authenticated";
GRANT ALL ON TABLE "public"."cedar_chunks" TO "service_role";



GRANT ALL ON SEQUENCE "public"."cedar_chunks_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."cedar_chunks_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cedar_chunks_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."cedar_document_metadata" TO "anon";
GRANT ALL ON TABLE "public"."cedar_document_metadata" TO "authenticated";
GRANT ALL ON TABLE "public"."cedar_document_metadata" TO "service_role";



GRANT ALL ON SEQUENCE "public"."cedar_document_metadata_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."cedar_document_metadata_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cedar_document_metadata_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."cedar_documents" TO "anon";
GRANT ALL ON TABLE "public"."cedar_documents" TO "authenticated";
GRANT ALL ON TABLE "public"."cedar_documents" TO "service_role";



GRANT ALL ON SEQUENCE "public"."cedar_documents_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."cedar_documents_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cedar_documents_id_seq" TO "service_role";



GRANT ALL ON SEQUENCE "public"."cedar_documents_id_seq1" TO "anon";
GRANT ALL ON SEQUENCE "public"."cedar_documents_id_seq1" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cedar_documents_id_seq1" TO "service_role";



GRANT ALL ON TABLE "public"."cedar_runs" TO "anon";
GRANT ALL ON TABLE "public"."cedar_runs" TO "authenticated";
GRANT ALL ON TABLE "public"."cedar_runs" TO "service_role";



GRANT ALL ON SEQUENCE "public"."cedar_runs_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."cedar_runs_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cedar_runs_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."conversations" TO "anon";
GRANT ALL ON TABLE "public"."conversations" TO "authenticated";
GRANT ALL ON TABLE "public"."conversations" TO "service_role";



GRANT ALL ON TABLE "public"."course_names" TO "anon";
GRANT ALL ON TABLE "public"."course_names" TO "authenticated";
GRANT ALL ON TABLE "public"."course_names" TO "service_role";



GRANT ALL ON TABLE "public"."cropwizard-papers" TO "anon";
GRANT ALL ON TABLE "public"."cropwizard-papers" TO "authenticated";
GRANT ALL ON TABLE "public"."cropwizard-papers" TO "service_role";



GRANT ALL ON SEQUENCE "public"."cropwizard-papers_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."cropwizard-papers_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cropwizard-papers_id_seq" TO "service_role";



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



GRANT ALL ON TABLE "public"."doc_groups_sharing" TO "anon";
GRANT ALL ON TABLE "public"."doc_groups_sharing" TO "authenticated";
GRANT ALL ON TABLE "public"."doc_groups_sharing" TO "service_role";



GRANT ALL ON SEQUENCE "public"."doc_groups_sharing_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."doc_groups_sharing_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."doc_groups_sharing_id_seq" TO "service_role";



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



GRANT ALL ON TABLE "public"."email-newsletter" TO "anon";
GRANT ALL ON TABLE "public"."email-newsletter" TO "authenticated";
GRANT ALL ON TABLE "public"."email-newsletter" TO "service_role";



GRANT ALL ON TABLE "public"."folders" TO "anon";
GRANT ALL ON TABLE "public"."folders" TO "authenticated";
GRANT ALL ON TABLE "public"."folders" TO "service_role";



GRANT ALL ON TABLE "public"."hypopg_list_indexes" TO "anon";
GRANT ALL ON TABLE "public"."hypopg_list_indexes" TO "authenticated";
GRANT ALL ON TABLE "public"."hypopg_list_indexes" TO "service_role";
GRANT ALL ON TABLE "public"."hypopg_list_indexes" TO "postgres";



GRANT ALL ON TABLE "public"."hypopg_hidden_indexes" TO "postgres";
GRANT ALL ON TABLE "public"."hypopg_hidden_indexes" TO "anon";
GRANT ALL ON TABLE "public"."hypopg_hidden_indexes" TO "authenticated";
GRANT ALL ON TABLE "public"."hypopg_hidden_indexes" TO "service_role";



GRANT ALL ON TABLE "public"."llm-convo-monitor" TO "anon";
GRANT ALL ON TABLE "public"."llm-convo-monitor" TO "authenticated";
GRANT ALL ON TABLE "public"."llm-convo-monitor" TO "service_role";



GRANT ALL ON SEQUENCE "public"."llm-convo-monitor_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."llm-convo-monitor_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."llm-convo-monitor_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."llm-guided-contexts" TO "anon";
GRANT ALL ON TABLE "public"."llm-guided-contexts" TO "authenticated";
GRANT ALL ON TABLE "public"."llm-guided-contexts" TO "service_role";



GRANT ALL ON TABLE "public"."llm-guided-docs" TO "anon";
GRANT ALL ON TABLE "public"."llm-guided-docs" TO "authenticated";
GRANT ALL ON TABLE "public"."llm-guided-docs" TO "service_role";



GRANT ALL ON TABLE "public"."llm-guided-sections" TO "anon";
GRANT ALL ON TABLE "public"."llm-guided-sections" TO "authenticated";
GRANT ALL ON TABLE "public"."llm-guided-sections" TO "service_role";



GRANT ALL ON TABLE "public"."messages" TO "anon";
GRANT ALL ON TABLE "public"."messages" TO "authenticated";
GRANT ALL ON TABLE "public"."messages" TO "service_role";



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



GRANT ALL ON TABLE "public"."pre_authorized_api_keys" TO "anon";
GRANT ALL ON TABLE "public"."pre_authorized_api_keys" TO "authenticated";
GRANT ALL ON TABLE "public"."pre_authorized_api_keys" TO "service_role";



GRANT ALL ON SEQUENCE "public"."pre-authorized-api-keys_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."pre-authorized-api-keys_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."pre-authorized-api-keys_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."project_stats" TO "anon";
GRANT ALL ON TABLE "public"."project_stats" TO "authenticated";
GRANT ALL ON TABLE "public"."project_stats" TO "service_role";



GRANT ALL ON SEQUENCE "public"."project_stats_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."project_stats_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."project_stats_id_seq" TO "service_role";



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



GRANT ALL ON TABLE "public"."pubmed_daily_update" TO "anon";
GRANT ALL ON TABLE "public"."pubmed_daily_update" TO "authenticated";
GRANT ALL ON TABLE "public"."pubmed_daily_update" TO "service_role";



GRANT ALL ON SEQUENCE "public"."pubmed_daily_update_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."pubmed_daily_update_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."pubmed_daily_update_id_seq" TO "service_role";



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
