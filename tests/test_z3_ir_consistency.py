"""Regression tests for Z3 IR verification."""

import pytest

from scripts.verify_ir_with_z3 import verify_ir_entry


CASES = {'correct_calculation': ({'variables': {'x': 10},
                          'equations': [{'lhs': 'y', 'rhs': 'x + 5'}],
                          'claimed_answer': {'target_variable': 'y',
                                             'predicted_value': 15,
                                             'tolerance': 0.01}},
                         'PASS'),
 'incorrect_calculation': ({'variables': {'x': 10},
                            'equations': [{'lhs': 'y', 'rhs': 'x + 5'}],
                            'claimed_answer': {'target_variable': 'y',
                                               'predicted_value': 20,
                                               'tolerance': 0.01}},
                           'FAIL'),
 'contradictory_equations': ({'variables': {'x': 10},
                              'equations': [{'lhs': 'y', 'rhs': 'x + 5'},
                                            {'lhs': 'y', 'rhs': 'x + 10'}],
                              'claimed_answer': {'target_variable': 'y',
                                                 'predicted_value': 100,
                                                 'tolerance': 0.01}},
                             'FAIL'),
 'consistent_multiple_equations': ({'variables': {'x': 10},
                                    'equations': [{'lhs': 'y', 'rhs': 'x + 5'},
                                                  {'lhs': 'y',
                                                   'rhs': 'x * 1.5'}],
                                    'claimed_answer': {'target_variable': 'y',
                                                       'predicted_value': 15,
                                                       'tolerance': 0.01}},
                                   'PASS'),
 'multi_step_calculation': ({'variables': {'x': 10},
                             'equations': [{'lhs': 'z', 'rhs': 'x * 2'},
                                           {'lhs': 'y', 'rhs': 'z + 5'}],
                             'claimed_answer': {'target_variable': 'y',
                                                'predicted_value': 25,
                                                'tolerance': 0.01}},
                            'PASS'),
 'within_tolerance': ({'variables': {'x': 10},
                       'equations': [{'lhs': 'y', 'rhs': 'x + 5'}],
                       'claimed_answer': {'target_variable': 'y',
                                          'predicted_value': 15.005,
                                          'tolerance': 0.01}},
                      'PASS'),
 'outside_tolerance': ({'variables': {'x': 10},
                        'equations': [{'lhs': 'y', 'rhs': 'x + 5'}],
                        'claimed_answer': {'target_variable': 'y',
                                           'predicted_value': 15.02,
                                           'tolerance': 0.01}},
                       'FAIL'),
 'negative_result': ({'variables': {'x': 10},
                      'equations': [{'lhs': 'y', 'rhs': 'x - 20'}],
                      'claimed_answer': {'target_variable': 'y',
                                         'predicted_value': -10,
                                         'tolerance': 0.01}},
                     'PASS'),
 'missing_equations': ({'variables': {'x': 10},
                        'equations': [],
                        'claimed_answer': {'target_variable': 'y',
                                           'predicted_value': 15,
                                           'tolerance': 0.01}},
                       'NOT_APPLICABLE'),
 'underdetermined_result': ({'variables': {'x': 10},
                             'equations': [{'lhs': 'y', 'rhs': 'y'}],
                             'claimed_answer': {'target_variable': 'y',
                                                'predicted_value': 15,
                                                'tolerance': 0.01}},
                            'FAIL')}


@pytest.mark.parametrize("name", CASES)
def test_ir_verification(name):
    case, expected_status = CASES[name]
    result = verify_ir_entry(case)
    assert result["status"] == expected_status, result
