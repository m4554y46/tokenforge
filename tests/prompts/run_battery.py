# -*- coding: utf-8 -*-
"""TokenForge Frontier Test Battery - CLI runner + pytest wrapper."""

import argparse
import json
import os
import sys
import yaml
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.abspath('.'))

BATTERY_DIR = Path(__file__).parent
THRESHOLDS_PATH = BATTERY_DIR / 'thresholds.yaml'
RESULTS_DIR = BATTERY_DIR / 'results'
CATEGORIES = {
    '00': '00_legacy',
    '01': '01_compressibility',
    '02': '02_structural',
    '03': '03_semantic',
    '04': '04_adversarial',
    '05': '05_domain',
    '06': '06_crosslingual',
    '07': '07_ace_decision',
    '08': '08_regression',
    '09': '09_calibration',
}


def load_thresholds():
    with open(THRESHOLDS_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_category(cat_key):
    cat_file = CATEGORIES.get(cat_key, cat_key)
    path = BATTERY_DIR / f'{cat_file}.yaml'
    if not path.exists():
        path = BATTERY_DIR / '00_legacy' / f'{cat_file}.yaml'
    if not path.exists():
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def list_prompts():
    print('TokenForge Frontier Test Battery - Prompt Inventory\n')
    for cat_key in sorted(CATEGORIES.keys()):
        data = load_category(cat_key)
        if not data:
            continue
        cat_name = list(data.keys())[0]
        prompts = data[cat_name].get('prompts', {})
        desc = data[cat_name].get('description', '')
        print(f'{cat_key}. {cat_name} - {len(prompts)} prompts')
        if desc:
            print(f'   {desc}')
        for pid, info in prompts.items():
            diff = info.get('difficulty', '?')
            toks = info.get('tokens', '?')
            lang = info.get('languages', [])
            lang_str = ','.join(lang) if lang else '-'
            notes = info.get('notes', '')
            print(f'   {pid:30s} d={diff:2d} t={str(toks):>5s} [{lang_str:8s}] {notes}')
        print()
    total = sum(
        len(load_category(k)[list(load_category(k).keys())[0]].get('prompts', {}))
        for k in CATEGORIES if load_category(k)
    )
    print(f'Total categories: {len(CATEGORIES)}')
    print(f'Total prompts: {total}')


def evaluate_contract(check, result, original_text):
    check = check.strip()
    if check in ('negations_preserved',):
        compressed = result.get('compressed', '')
        negation_words = ['not', 'never', 'no', 'forbidden', 'except', 'unless']
        for word in negation_words:
            if word in original_text.lower():
                if word not in compressed.lower():
                    return False
        return True
    if check == 'no_crash':
        return result.get('error') is None
    if check == 'output_not_empty':
        return len(result.get('compressed', '').strip()) > 0
    return True


def run_prompt(prompt_id, prompt_info, thresholds, spc_instance=None):
    text = prompt_info.get('text', '')
    contract_checks = prompt_info.get('contract_check', [])
    result = {
        'id': prompt_id,
        'difficulty': prompt_info.get('difficulty', 0),
        'expected_tokens': prompt_info.get('tokens', 0),
        'actual_tokens': len(text.split()),
        'passed': True,
        'contracts': {},
        'error': None,
    }
    if not text.strip():
        result['compressed'] = ''
        result['error'] = 'empty_input'
        return result
    if spc_instance:
        try:
            output = spc_instance.compile(text)
            compressed = output.compressed if output.compressed else text
            result['compressed'] = compressed
            result['compression_ratio'] = len(compressed) / max(len(text), 1)
            if output.validation:
                result['validation_passed'] = output.validation.passed
        except Exception as e:
            result['error'] = str(e)
            result['passed'] = False
            return result
    for check in contract_checks:
        check_result = evaluate_contract(check, result, text)
        result['contracts'][check] = check_result
        if not check_result:
            result['passed'] = False
    return result


def run_category(cat_key, thresholds, spc_instance=None):
    data = load_category(cat_key)
    if not data:
        print(f'Category {cat_key} not found.')
        return []
    cat_name = list(data.keys())[0]
    prompts = data[cat_name].get('prompts', {})
    results = []
    print()
    print('=' * 60)
    print(f'Category: {cat_name} ({len(prompts)} prompts)')
    print('=' * 60)
    for pid, info in prompts.items():
        r = run_prompt(pid, info, thresholds, spc_instance)
        results.append(r)
        status = 'PASS' if r['passed'] else 'FAIL'
        err = f' - {r["error"]}' if r.get('error') else ''
        print(f'  [{status}] {pid} (d={r["difficulty"]}){err}')
    passed = sum(1 for r in results if r['passed'])
    print(f'  -> {passed}/{len(results)} passed')
    return results


def generate_report(all_results, output_format='all'):
    timestamp = datetime.now().isoformat()
    total = sum(len(v) for v in all_results.values())
    passed = sum(sum(1 for r in v if r['passed']) for v in all_results.values())
    report = {
        'timestamp': timestamp,
        'total_prompts': total,
        'passed': passed,
        'failed': total - passed,
        'categories': {},
    }
    for cat_key, results in all_results.items():
        cat_passed = sum(1 for r in results if r['passed'])
        report['categories'][cat_key] = {
            'total': len(results),
            'passed': cat_passed,
            'failed': len(results) - cat_passed,
            'results': results,
        }
    if output_format in ('json', 'all'):
        report_path = RESULTS_DIR / f'report_{timestamp[:10]}.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f'Report saved: {report_path}')
    if output_format in ('console', 'all'):
        print()
        print('=' * 60)
        print('FRONTIER TEST BATTERY - RAPPORT FINAL')
        print('=' * 60)
        print(f'Date: {timestamp}')
        print(f'Total: {total} prompts, FAIL: {total - passed}, PASS: {passed}')
        for cat_key, results in all_results.items():
            cat_passed = sum(1 for r in results if r['passed'])
            print(f'  {cat_key}: {cat_passed}/{len(results)} passed')
    if output_format in ('md', 'all'):
        md_path = RESULTS_DIR / f'report_{timestamp[:10]}.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f'# Rapport Batterie Frontiere - {timestamp[:10]}\n\n')
            f.write(f'**Total:** {total} - **PASS:** {passed} - **FAIL:** {total - passed}\n\n')
            f.write('| Categorie | Total | PASS | FAIL |\n')
            f.write('|-----------|-------|------|------|\n')
            for cat_key, results in sorted(all_results.items()):
                cat_passed = sum(1 for r in results if r['passed'])
                cat_failed = len(results) - cat_passed
                f.write(f'| {cat_key} | {len(results)} | {cat_passed} | {cat_failed} |\n')
        print(f'Markdown report saved: {md_path}')
    return report


def main():
    parser = argparse.ArgumentParser(description='TokenForge Frontier Test Battery')
    parser.add_argument('--all', action='store_true', help='Run all categories')
    parser.add_argument('--category', type=str, help='Run specific category (e.g. 03)')
    parser.add_argument('--legacy', action='store_true', help='Run legacy prompts only')
    parser.add_argument('--ci', action='store_true', help='Strict CI mode')
    parser.add_argument('--list', action='store_true', help='List all prompts')
    parser.add_argument('--output', type=str, default='all', choices=['console', 'json', 'md', 'all'])
    args = parser.parse_args()
    if args.list:
        list_prompts()
        return
    print('TokenForge Frontier Test Battery v1.0\n')
    thresholds = load_thresholds()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    spc = None
    try:
        from backend.spc.pipeline import SPC
        from backend.spc.profiles import BALANCED
        spc = SPC(profile=BALANCED)
        print('SPC pipeline loaded (profile BALANCED)')
    except ImportError:
        print('SPC pipeline not available - metadata-only mode')
    all_results = {}
    if args.category:
        cats_to_run = [args.category]
    elif args.legacy:
        cats_to_run = ['00']
    elif args.all:
        cats_to_run = sorted(CATEGORIES.keys())
    else:
        print('Usage: run_battery.py --all | --category | --legacy | --list')
        return
    for cat_key in cats_to_run:
        results = run_category(cat_key, thresholds, spc)
        all_results[cat_key] = results
    report = generate_report(all_results, args.output)
    if args.ci and report['failed'] > 0:
        print(f'CI MODE: {report["failed"]} failures detected - exiting with code 1')
        sys.exit(1)


if __name__ == '__main__':
    main()
