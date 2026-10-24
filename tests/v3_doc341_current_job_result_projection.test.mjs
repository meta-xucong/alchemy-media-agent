import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../src_skeleton/app/static/app.js", import.meta.url),
  "utf8",
);
const reviewStart = source.indexOf("function v3ReviewOnlyJobImageItems(");
const reviewEnd = source.indexOf("\nfunction mergeV3ReviewImageSources", reviewStart);
assert.ok(reviewStart >= 0 && reviewEnd > reviewStart, "current-job review projection must be present");
const reviewSource = source.slice(reviewStart, reviewEnd);
const boardStart = source.indexOf("function renderV3ResultBoard(job)");
const boardEnd = source.indexOf("\nfunction v3OutputImageCandidates", boardStart);
assert.ok(boardStart >= 0 && boardEnd > boardStart, "result board renderer must be present");
const boardSource = source.slice(boardStart, boardEnd);
const cardStart = source.indexOf("function appendV3ReviewOnlyResultCards(");
const cardEnd = source.indexOf("\nfunction mergeV3ReviewImageSources", cardStart);
assert.ok(cardStart >= 0 && cardEnd > cardStart, "review-only result card renderer must be present");
const cardSource = source.slice(cardStart, cardEnd);

function projectReviewItems(job, items, reviewOutputIds = []) {
  const context = {
    v3State: { currentProject: { project_id: "doc341-project" } },
    v3EcommerceReviewWithheldFinalizationOperation: () => false,
    v3JobDeliveryWithheld: () => false,
    v3FailureArtifactExpired: () => false,
    v3StoredProjectReviewOutputItems: () => items,
    v3ReviewOutputIdSet: () => new Set(reviewOutputIds),
    mergeV3ReviewImageSources: (...sources) => sources.flat(),
    v3OutputImageCandidates: (item) => item.preview_url ? [item.preview_url] : [],
    v3OutputItemIdentity: (item) => item.output_id,
    v3ProjectOutputStateMap: () => new Map(),
    v3ReviewRank: () => 0,
  };
  vm.runInNewContext(reviewSource, context);
  return context.v3ReviewOnlyJobImageItems(job);
}

test("partial current job keeps its latest review-only sibling and hides stale/superseded outputs", () => {
  const job = { job_id: "current-job", status: "generated", metadata: {} };
  const items = [
    {
      output_id: "old-job-review",
      job_id: "old-job",
      preview_url: "https://images.example/old-job-review.png",
      metadata: { delivery_attempt_index: 1, delivery_final_attempt_index: 1 },
    },
    {
      output_id: "current-review",
      job_id: "current-job",
      review_only: true,
      preview_url: "https://images.example/current-review.png",
      metadata: { delivery_attempt_index: 1, delivery_final_attempt_index: 1 },
    },
    {
      output_id: "superseded-review",
      job_id: "current-job",
      review_only: true,
      delivery_state: "superseded",
      preview_url: "https://images.example/superseded-review.png",
      metadata: {
        delivery_attempt_index: 0,
        delivery_final_attempt_index: 1,
        retry_superseded: true,
      },
    },
    {
      output_id: "mismatched-attempt-review",
      job_id: "current-job",
      review_only: true,
      preview_url: "https://images.example/mismatched-attempt-review.png",
      metadata: { delivery_attempt_index: 0, delivery_final_attempt_index: 1 },
    },
    {
      output_id: "missing-lineage-review",
      job_id: "current-job",
      review_only: true,
      preview_url: "https://images.example/missing-lineage-review.png",
      metadata: {},
    },
    {
      output_id: "id-bound-current-review",
      job_id: "current-job",
      review_only: true,
      preview_url: "https://images.example/id-bound-current-review.png",
      metadata: {},
    },
  ];

  const projected = projectReviewItems(job, items, ["id-bound-current-review"]);

  assert.deepEqual(projected.map((item) => item.output_id), ["current-review", "id-bound-current-review"]);
  assert.ok(!projected.some((item) => item.output_id === "superseded-review"));
  assert.ok(!projected.some((item) => item.output_id === "mismatched-attempt-review"));
  assert.ok(!projected.some((item) => item.output_id === "missing-lineage-review"));
});

test("result board adds only requested-count review cards without delivery actions", () => {
  assert.match(boardSource, /const expectedCount = v3ExpectedImageCountForJob\(job\)/);
  assert.match(boardSource, /v3ReviewOnlyJobImageItems\(job\)/);
  assert.match(boardSource, /仅供复核/);
  assert.match(boardSource, /\.slice\(0,\s*Math\.max\(0,\s*expectedCount\s*-\s*items\.length\)\)/);
  assert.match(boardSource, /appendV3ReviewOnlyResultCards\(els\.v3ResultBoard,\s*reviewItems/);
  assert.match(cardSource, /仅供复核/);
  assert.doesNotMatch(cardSource, /data-v3-result-action/);
});
