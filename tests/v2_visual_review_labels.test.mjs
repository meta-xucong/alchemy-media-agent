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
  function functionSource(name) {
    const first = source.indexOf(`function ${name}(`);
    return source.slice(source.slice(first - 6, first) === 'async ' ? first - 6 : first, source.indexOf('\nfunction ', first + 10));
  }
  function node(tag) {
    return {tag, textContent:'', children:[], classList:{toggle() {}}, closest() {return null;},
      append(...items) {this.children.push(...items);}, appendChild(item) {this.children.push(item);}, addEventListener() {}};
  }
  const plainText = (item) => item.textContent + item.children.map(plainText).join(' ');
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
    assert.ok(source.includes('appendV2ReviewDetails(meta, review);'));
    assert.ok(!source.includes('Math.round((review.score || 0) * 100)'));
  });
  test(`${path}: API-unknown failure notice is visible and terminal`, () => {
    const first = source.indexOf('function v2RunNotice(');
    const end = source.indexOf('\nfunction ', first + 10);
    const context = vm.createContext({});
    vm.runInContext(source.slice(first, end), context);
    const message = 'API 执行结果未知（请求可能已到达上游）；系统不会自动重试，以免重复生成或扣费。本次未收到可展示的图片。';
    const notice = context.v2RunNotice({status:'failed',next_actions:[message],
      generation_jobs:[{status:'failed',outputs:[],error:{message}}]});
    assert.equal(notice.type,'error');
    assert.match(notice.message,/结果未知/);
    assert.match(notice.message,/不会自动重试/);
    assert.match(notice.message,/未收到可展示的图片/);
  });
  test(`${path}: final notice and real history/lightbox consumers expose review and retain the image`, async () => {
    const grid = node('div');
    let lightbox;
    Object.assign(context, {
      document:{createElement:node}, els:{v2HistoryGrid:grid,v2HistoryCount:node('span')},
      v2State:{historyFavoritesOnly:false,historyRenderLimit:24}, historyWindowSize:24,
      historyDemandVisible:()=>true, clearHistoryMedia:()=>{}, historyDemandState:()=>({mode:'all'}),
      historyFavoritesDemanded:()=>false, isRenderableV2HistoryImage:()=>true, historyWindowLabel:()=>'',
      v2HistoryCardPrompt:()=>'', v2HistoryImageCandidates:(item)=>[item.url], bindImageWithFallback:(image,urls)=>{image.url=urls[0];},
      historyMediaDemand:()=>true, createFavoriteButton:()=>node('button'),
      historyDetailText:()=>'', historyRecordLabel:()=>'', v2HistoryProviderResultText:()=>'', formatDate:()=>'',
      v2ExplicitDownloadUrl:(item)=>item.url,v2HistoryFormat:()=> 'png',bindDownloadLink:()=>{},historyItemCanDelete:()=>false,
      renderHistoryWindowNavigation:()=>{}, v2HistoryImageUrl:(item)=>item.url,v2HistoryPreviewCandidates:(item)=>[item.url],
      v2PromptTextFromHistory:()=>'', openImageLightbox:(data)=>{lightbox=data;},
      v2ProviderResultText:()=> 'Bridge',
    });
    for (const name of ['v2RunNotice','renderV2History','openV2HistoryLightbox']) vm.runInContext(functionSource(name),context);
    const review = {analysis_mode:'vision_model',decision:'needs_review',revision_directives:['Only the left shoulder was requested.']};
    const item = {output_id:'output',job_id:'job',url:'/same-image',review,metadata:{live:true}};
    const notice = context.v2RunNotice({status:'completed',generation_jobs:[{status:'completed',outputs:[item]}]});
    assert.equal(notice.type,'warning');
    assert.match(notice.message,/需确认/);
    context.renderV2History([item]);
    assert.match(plainText(grid),/视觉审核需确认，图片已保留/);
    assert.match(plainText(grid),/Only the left shoulder/);
    assert.equal(grid.children[0].children[0].children[0].url,'/same-image');
    context.openV2HistoryLightbox(item);
    assert.equal(lightbox.url,'/same-image');
    assert.match(lightbox.meta,/需确认/);
    assert.match(lightbox.meta,/Only the left shoulder/);
    const notices = [];
    const finished = [];
    Object.assign(context, {
      simpleModeState:{v2:{files:[]}}, simplePromptOrFallback:()=> 'Requested portrait',
      setSimpleRunning:()=>{}, startSimpleProgress:()=>{}, renderV2SimpleCaseSummary:()=>{},
      updateSimpleNotice:(...args)=>notices.push(args), finishSimpleProgress:(...args)=>finished.push(args),
      snapshotV2Context:()=>({}), restoreV2Context:()=>{}, inferSimpleAssetRoles:()=>[],
      setV2PromptTransformMode:()=>{}, restoreInput:()=>{},setCheckedByDataset:()=>{},
      updateV2FavoriteReferenceLabel:()=>{},renderV2Templates:()=>{},renderV2AssetPanel:()=>{},setSimpleProgress:()=>{},
      updateSimpleProgressFromV2Run:()=>{},runV2Creative:async()=>({status:'completed',generation_jobs:[{status:'completed',outputs:[item]}]}),
      friendlyError:(error)=>String(error),
    });
    for (const key of ['v2PromptInput','v2CountInput','v2CountValue','v2SelectedTemplateLabel']) context.els[key]=node('input');
    context.document.querySelectorAll=()=>[];
    vm.runInContext(functionSource('runV2SimpleMode'),context);
    await context.runV2SimpleMode();
    assert.equal(notices.at(-1)[2],'warning');
    assert.match(notices.at(-1)[1],/需确认/);
    assert.equal(finished.at(-1)[1],'completed');
    assert.equal(finished.at(-1)[3],'warning');
  });
}
