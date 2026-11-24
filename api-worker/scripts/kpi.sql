-- Weekly KPIs (product/measurement-plan.md §3) over Analytics Engine dataset specsheet_requests. Run by scripts/kpi.sh, one block per
-- `-- kpi: <name>` marker, last 7 days, traffic class real only (blob7). Field map (src/metrics.ts toDataPoint):
--   index1 kind (api|mcp|beacon|ops); blob1 route; blob2 category; blob3 status; blob4 outcome; blob5 UA family; blob6 mode[:would_be_paid key];
--   blob7 traffic; blob8 release; blob9 MCP client name; blob10 cid; blob11 filter keys | event:detail | redacted miss text;
--   double1 results; double2 bytes; double3 wall ms; double4 cache hit. Counts use SUM(_sample_interval) (AE samples at high volume).
-- Not in AE (read from the Cloudflare dashboard / CF Web Analytics): DO rows written, human visitors, referrers; corrections from GitHub.

-- kpi: ok_calls_per_day
SELECT toDate(timestamp) AS day, index1 AS kind, SUM(_sample_interval) AS ok_results
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND index1 IN ('api', 'mcp') AND blob4 = 'ok_results'
GROUP BY day, kind ORDER BY day, kind

-- kpi: empty_and_match_fail_rates
SELECT toDate(timestamp) AS day,
  SUM(IF(blob4 = 'ok_empty', _sample_interval, 0)) / SUM(IF(blob4 IN ('ok_results', 'ok_empty') AND blob1 IN ('/v1/query', '/mcp:query_specs'), _sample_interval, 0)) AS query_empty_rate,
  SUM(IF(blob4 = 'match_fail', _sample_interval, 0)) / SUM(IF(blob1 IN ('/v1/match', '/mcp:match_product') AND blob4 IN ('ok_results', 'match_fail'), _sample_interval, 0)) AS match_fail_rate
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND index1 IN ('api', 'mcp')
GROUP BY day ORDER BY day

-- kpi: p95_wall_ms_per_route
SELECT blob1 AS route, quantileWeighted(0.95)(double3, _sample_interval) AS p95_wall_ms, SUM(_sample_interval) AS calls
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND index1 IN ('api', 'mcp', 'beacon')
GROUP BY route ORDER BY calls DESC

-- kpi: error_rates
SELECT toDate(timestamp) AS day,
  SUM(IF(blob3 = '429', _sample_interval, 0)) / SUM(_sample_interval) AS rate_429,
  SUM(IF(blob3 LIKE '5%' AND blob4 = 'error', _sample_interval, 0)) / SUM(_sample_interval) AS rate_5xx,
  SUM(IF(blob4 = 'breaker', _sample_interval, 0)) AS breaker_refusals
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND index1 IN ('api', 'mcp', 'beacon')
GROUP BY day ORDER BY day

-- kpi: quota_degraded
SELECT toDate(timestamp) AS day, SUM(_sample_interval) AS quota_degraded
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND index1 = 'ops' AND blob1 = 'quota_degraded'
GROUP BY day ORDER BY day

-- kpi: bytes_and_cache
SELECT toDate(timestamp) AS day, SUM(double2 * _sample_interval) AS response_bytes,
  SUM(double4 * _sample_interval) / SUM(_sample_interval) AS cache_hit_rate
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND index1 IN ('api', 'mcp')
GROUP BY day ORDER BY day

-- kpi: free_allowance_use
-- all traffic classes: every point is a billed Worker request and an AE write; data + beacon calls are DO requests (one each).
SELECT toDate(timestamp) AS day, SUM(_sample_interval) AS points,
  SUM(_sample_interval) / 100000 AS worker_req_and_ae_write_share_of_free_day,
  SUM(IF(blob1 IN ('/v1/query', '/v1/changes', '/v1/match', '/v1/miss', '/v1/event') OR blob1 LIKE '/mcp:%', _sample_interval, 0)) / 100000 AS do_request_share_approx
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY
GROUP BY day ORDER BY day

-- kpi: agent_cids_per_day
SELECT toDate(timestamp) AS day, COUNT(DISTINCT blob10) AS non_browser_cids
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND blob10 != 'none'
  AND (index1 = 'mcp' OR blob5 NOT IN ('browser'))
GROUP BY day ORDER BY day

-- kpi: mcp_client_names_3_days
SELECT blob9 AS client, COUNT(DISTINCT toDate(timestamp)) AS days_seen
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND index1 = 'mcp' AND blob9 != '' AND blob9 != 'other'
GROUP BY client HAVING days_seen >= 3 ORDER BY days_seen DESC

-- kpi: killer_query_and_ctr
SELECT toDate(timestamp) AS day,
  SUM(IF(blob11 LIKE 'killer_query:%', _sample_interval, 0)) AS killer_query_runs,
  SUM(IF(blob11 LIKE 'source_click:%' OR blob11 LIKE 'product_view:%', _sample_interval, 0)) / SUM(IF(blob11 LIKE 'killer_query:%', _sample_interval, 0)) AS ctr
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND index1 = 'beacon'
GROUP BY day ORDER BY day

-- kpi: killer_query_presets
SELECT blob11 AS preset, SUM(_sample_interval) AS runs, SUM(IF(double1 = 0, _sample_interval, 0)) / SUM(_sample_interval) AS zero_result_rate
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND index1 = 'beacon' AND blob11 LIKE 'killer_query:%'
GROUP BY preset ORDER BY runs DESC

-- kpi: spec_unknown_shown_top
SELECT blob2 AS category, blob11 AS spec, SUM(_sample_interval) AS shown
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND blob11 LIKE 'spec_unknown_shown:%'
GROUP BY category, spec ORDER BY shown DESC LIMIT 50

-- kpi: misses_k3
-- k>=3 rule: only texts sent by >= 3 distinct cids this week leave AE. Below that nothing is exported.
SELECT blob2 AS category, blob11 AS miss_text, COUNT(DISTINCT blob10) AS cids
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND blob1 = '/v1/miss' AND blob10 != 'none'
GROUP BY category, miss_text HAVING cids >= 3 ORDER BY cids DESC

-- kpi: would_be_paid_per_day
SELECT toDate(timestamp) AS day, blob6 AS mode_route, SUM(_sample_interval) AS calls
FROM specsheet_requests WHERE timestamp > NOW() - INTERVAL '7' DAY AND blob7 = 'real' AND blob6 LIKE '%:%' AND blob4 IN ('ok_results', 'ok_empty', 'match_fail')
GROUP BY day, mode_route ORDER BY day
