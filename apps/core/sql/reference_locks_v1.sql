-- REFERENCE_LOCKS_V1. Installed only by reviewed maintenance tooling.
-- Installer owns transaction, private schema/role setup and explicit EXECUTE grants.
-- No dynamic SQL, business DML, price locks, transaction control or business output.
CREATE FUNCTION sales_ai_locks.lock_feedback_references(customer_id bigint, recommendation_id bigint)
RETURNS void LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
SET row_security = on
AS $body$
DECLARE
    locked_product_id bigint;
BEGIN
    IF customer_id IS NULL OR customer_id <= 0 OR recommendation_id IS NULL OR recommendation_id <= 0 THEN
        RAISE EXCEPTION 'Invalid reference lock arguments' USING ERRCODE = '22023';
    END IF;
    SELECT r.product_id INTO locked_product_id
    FROM public.recommendations_customerrecommendation AS r
    WHERE r.id = recommendation_id AND r.customer_id = lock_feedback_references.customer_id
    FOR UPDATE OF r;
    IF NOT FOUND THEN RETURN; END IF;
    PERFORM p.id FROM public.products_product AS p WHERE p.id = locked_product_id FOR UPDATE OF p;
END
$body$;

CREATE FUNCTION sales_ai_locks.lock_submission_references(customer_id bigint, product_ids bigint[])
RETURNS void LANGUAGE plpgsql VOLATILE PARALLEL UNSAFE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
SET row_security = on
AS $body$
DECLARE
    locked_grade_id bigint;
    v_product_id bigint;
BEGIN
    IF customer_id IS NULL OR customer_id <= 0 OR product_ids IS NULL
       OR pg_catalog.cardinality(product_ids) > 50
       OR COALESCE(pg_catalog.array_ndims(product_ids), 1) <> 1 THEN
        RAISE EXCEPTION 'Invalid reference lock arguments' USING ERRCODE = '22023';
    END IF;
    IF pg_catalog.array_position(product_ids, NULL) IS NOT NULL
       OR EXISTS (SELECT 1 FROM pg_catalog.unnest(product_ids) AS x(id) WHERE x.id <= 0) THEN
        RAISE EXCEPTION 'Invalid reference lock arguments' USING ERRCODE = '22023';
    END IF;
    SELECT c.grade_id INTO locked_grade_id FROM public.customers_customer AS c
    WHERE c.id = lock_submission_references.customer_id FOR UPDATE OF c;
    IF NOT FOUND THEN RETURN; END IF;
    IF locked_grade_id IS NOT NULL THEN
        PERFORM g.id FROM public.customers_customergrade AS g WHERE g.id = locked_grade_id FOR UPDATE OF g;
    END IF;
    FOR v_product_id IN SELECT DISTINCT x.id FROM pg_catalog.unnest(product_ids) AS x(id) ORDER BY x.id LOOP
        PERFORM p.id FROM public.products_product AS p WHERE p.id = v_product_id FOR UPDATE OF p;
    END LOOP;
    FOR v_product_id IN SELECT DISTINCT x.id FROM pg_catalog.unnest(product_ids) AS x(id) ORDER BY x.id LOOP
        PERFORM i.id FROM public.inventory_inventory AS i WHERE i.product_id = v_product_id
        FOR UPDATE OF i;
    END LOOP;
END
$body$;

COMMENT ON FUNCTION sales_ai_locks.lock_feedback_references(bigint,bigint) IS 'REFERENCE_LOCKS_V1';
COMMENT ON FUNCTION sales_ai_locks.lock_submission_references(bigint,bigint[]) IS 'REFERENCE_LOCKS_V1';
REVOKE ALL ON FUNCTION sales_ai_locks.lock_feedback_references(bigint,bigint) FROM PUBLIC;
REVOKE ALL ON FUNCTION sales_ai_locks.lock_submission_references(bigint,bigint[]) FROM PUBLIC;
