from __future__ import annotations

import asyncio

import pytest

from app.agents import runtime
from app.repositories import repository
from app.schemas import CreateCreativeRunRequest, PromptCase
from app.services import case_intelligence
from app.services import claude_orchestrator
from app.services.poster_layout import poster_layout_requirements, requests_blank_poster_qr_space
from app.services.prompting import compose_prompt_plan


@pytest.mark.parametrize(
    ('has_matching_case', 'selected_template', 'explicit_layout', 'expected'),
    [
        (True, None, True, ['case_flyer']), (False, None, True, []),
        (False, None, False, []), (True, 'case_product', True, ['case_product']),
    ],
)
def test_dense_poster_uses_compatible_auto_case_and_preserves_manual_priority(
    monkeypatch, has_matching_case, selected_template, explicit_layout, expected,
):
    monkeypatch.setattr(case_intelligence, 'bootstrap_v2_repository', lambda **_: None)
    cases = [PromptCase(
        case_id='case_product', title='Dessert poster', category='poster', provider_id='test',
        index_version='local', source_url='https://example.test/product',
        raw_prompt='Dessert poster with a centered hero, subtle grid background, premium lighting and a short headline.',
        visual_features={'composition_type': 'centered_hero', 'contains_text': True},
        use_case_tags=['poster'], style_tags=['premium'], quality_score=1.0,
    )]
    if has_matching_case:
        cases.append(PromptCase(
            case_id='case_flyer', title='Dessert course flyer', category='poster', provider_id='test',
            index_version='local', source_url='https://example.test/flyer',
            raw_prompt='Dessert poster. Headline, price, two-column course list and a reserved QR code area.',
            visual_features={'composition_type': 'multi_panel', 'contains_text': True},
            use_case_tags=['poster'], style_tags=['premium'], quality_score=0.5,
        ))
    repository.upsert_cases(cases)
    if selected_template:
        original_orchestrator = runtime.orchestrate_creative_request

        def return_unlocked_mode(**kwargs):
            return original_orchestrator(**kwargs).model_copy(update={'mode': 'smart_enhance'})

        monkeypatch.setattr(runtime, 'orchestrate_creative_request', return_unlocked_mode)

    brief = 'Create a premium dessert course poster. Include a headline, price, class dates and registration details.'
    if explicit_layout:
        brief += ' Use a two-column course list. Do not include a QR code, but reserve a blank white QR code area.'
    run = asyncio.run(runtime.CreativeManagerRuntime().run(CreateCreativeRunRequest(
        user_prompt=brief,
        template_case_id=selected_template,
        output={'count': 1, 'provider_hint': 'mock_image'},
    )))

    assert run.status == 'completed'
    assert [case.case_id for case in run.selected_cases] == expected
    assert run.prompt_plan.user_variables['template_lock_enabled'] is bool(selected_template)
    if selected_template:
        assert run.mode == 'template_customize'
        assert run.prompt_plan.user_variables['visual_grammar_contract']['lock_strength'] == 'strong'
    if not expected:
        assert not run.prompt_plan.user_variables['visual_grammar_lock_enabled']
    if explicit_layout:
        assert 'Reserve the requested blank QR area' in run.prompt_plan.prompt
        assert 'Hard QR exclusion' not in run.prompt_plan.prompt
        assert 'Do not include QR codes, scan-code modules, QR placeholders' not in run.prompt_plan.prompt
        assert 'CONTENT EXTRACTION LOCK' not in run.prompt_plan.prompt
        assert 'empty QR placeholder' not in run.prompt_plan.negative_prompt
    if expected:
        assert not run.prompt_plan.user_variables['visual_grammar_contract']['source_layout_risk']['detected']


@pytest.mark.parametrize('brief', [
    'Simple poster. Do not use two columns or reserve a QR code area.',
    '简洁海报。不要使用双栏，不要预留二维码区域。',
])
def test_explicit_layout_opt_out_does_not_become_a_required_slot(brief):
    layout = poster_layout_requirements(brief)
    assert 'two_columns' not in layout
    assert 'qr_space' not in layout
    assert 'qr_space' in poster_layout_requirements('海报不要画二维码，但请预留白色二维码区域。')


def test_layout_cache_rejects_prior_case_selection_for_same_poster():
    request = CreateCreativeRunRequest(user_prompt='Course poster with two columns and a reserved QR area.')
    current = claude_orchestrator._cache_metadata(request=request, fallback_mode='smart_enhance', candidate_cases=[])
    old = {key: value for key, value in current.items() if key != 'poster_layout'}
    old['candidate_case_ids'] = ['case_old_product']
    assert claude_orchestrator._semantic_cache_score(current, old) == 0.0
    assert claude_orchestrator._semantic_cache_score(current, {**current, 'candidate_case_ids': ['case_flyer']}) == 0.0
    assert claude_orchestrator._semantic_cache_score(current, current) == 1.0


@pytest.mark.parametrize('brief', [
    'Poster. Use the supplied URL QR code in the QR code area.',
    'Poster. Reserve a QR code area for the QR code generated from my URL.',
])
def test_poster_qr_area_does_not_replace_a_request_for_an_actual_code(brief):
    assert 'qr_space' in poster_layout_requirements(brief)
    assert not requests_blank_poster_qr_space(brief)
    plan = compose_prompt_plan(mode='smart_enhance', user_prompt=brief, cases=[], output={'count': 1})
    assert 'REQUIRED QR SPACE' not in plan.prompt
