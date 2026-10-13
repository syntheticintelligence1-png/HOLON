-- The BigQuery alternative to `python -m holon historical fetch` (BUILD_PLAN I23; human answer Q5: BigQuery's public
-- Ethereum dataset is one of the allowed sources). Not run here: it needs Google Cloud credentials
-- (GOOGLE_APPLICATION_CREDENTIALS_JSON in the environment's secrets), which this environment does not have.
--
-- What it returns: every log of the Rollup proxy 0x759894ced0e6af42c26668076ffa84d02e3cef60 with one of I59's five
-- topics (spec/M2/lib/historical.json "events") over the codec window [19426587, 26179508] (I59's whole window), joined
-- with its transaction (calldata, sender, blob versioned hashes) and its receipt status. The result covers the log,
-- tx and receipt items of I59's index (results/M2/historical/index.json); blobs are not in BigQuery (the beacon API
-- and the blob archive serve them), and neither is historical state (fetch-state needs an archive RPC).
--
-- Usage: bq query --use_legacy_sql=false --format=json --max_rows=200000 < tools/historical_bigquery.sql
-- To compare with the index: each log's (transaction_hash, log_index) must name an index item of kind log, and the
-- topics and data must equal the snapshot object's (holon.historical.store canonical form, lowercase hex).

DECLARE proxy STRING DEFAULT '0x759894ced0e6af42c26668076ffa84d02e3cef60';
DECLARE from_block INT64 DEFAULT 19426587;
DECLARE to_block INT64 DEFAULT 26179508;

WITH topics AS (
  SELECT topic FROM UNNEST([
    '0x2c32d4ae151744d0bf0b9464a3e897a1d17ed2f1af71f7c9a75f12ce0d28238f',  -- CommitBatch(uint256,bytes32)
    '0x00cae2739091badfd91c373f0a16cede691e0cd25bb80cff77dd5caeb4710146',  -- RevertBatch(uint256,bytes32)
    '0x26ba82f907317eedc97d0cbef23de76a43dd6edb563bdb6e9407645b950a7a2d',  -- FinalizeBatch(uint256,bytes32,bytes32,bytes32)
    '0x3a6ea19df25b49e7624e313ce7c1ab23984238e93727260db56a81735b1b9976',  -- ChallengeState(uint64,address,uint256)
    '0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b'   -- Upgraded(address)
  ]) AS topic
),
proxy_logs AS (
  SELECT l.block_number, l.block_hash, l.transaction_hash, l.transaction_index, l.log_index, l.topics, l.data
  FROM `bigquery-public-data.crypto_ethereum.logs` AS l
  WHERE LOWER(l.address) = proxy
    AND l.block_number BETWEEN from_block AND to_block
    AND LOWER(l.topics[SAFE_OFFSET(0)]) IN (SELECT topic FROM topics)
)
SELECT
  pl.block_number,
  pl.block_hash,
  pl.transaction_hash,
  pl.transaction_index,
  pl.log_index,
  pl.topics,
  pl.data,
  t.from_address,
  t.to_address,
  t.input,
  t.value,
  t.blob_versioned_hashes,
  t.receipt_status
FROM proxy_logs AS pl
JOIN `bigquery-public-data.crypto_ethereum.transactions` AS t
  ON t.hash = pl.transaction_hash
 AND t.block_number BETWEEN from_block AND to_block
ORDER BY pl.block_number, pl.transaction_index, pl.log_index;
