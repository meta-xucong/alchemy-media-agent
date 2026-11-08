import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

for (const path of ['../src_skeleton/app/static/app.js', '../src_skeleton/app/mobile_static/mobile.js']) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8');
  const start = source.indexOf('function v2ReviewText(');
  const end = source.indexOf('\nfunction v2ReviewLabel(', start);
  const context = vm.createContext({});
  vm.runInContext(source.slice(start, end), context);
  test(`${path}: real and legacy review labels do not claim synthetic scores`, () => {
    const label = context.v2ReviewText;
    assert.equal(label({analysis_mode:'vision_model',decision:'pass'}), '视觉审核通过');
    for (const review of [null, {analysis_mode:'sdk_agent_metadata_fallback',decision:'pass',score:0.86},
      {analysis_mode:'metadata_rules',decision:'pass',score:0.86}, {analysis_mode:'pixel_file_and_contract',decision:'pass'}]) {
      assert.match(label(review), /未做视觉审核/);
      assert.doesNotMatch(label(review), /已通过|86|%/);
    }
    assert.match(label({analysis_mode:'vision_pending'}), /审核中/);
    assert.match(label({analysis_mode:'vision_unavailable'}), /人工确认/);
    assert.match(label({analysis_mode:'vision_model',decision:'needs_review'}), /图片已保留/);
    assert.ok(source.includes('const reviewText = v2ReviewText(review);'));
    assert.ok(!source.includes('Math.round((review.score || 0) * 100)'));
  });
}
