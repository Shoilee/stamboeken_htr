import json
import distance  
from difflib import SequenceMatcher
import numpy as np
from scipy.optimize import linear_sum_assignment

def calculate_normalized_information_distance(predicted_json, ground_truth_json):   
# --- Normalized edit distance function ---
    def normalized_edit_distance(s1, s2):
        if not s1 and not s2:
            return 0.0
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 0.0
        return distance.levenshtein(s1, s2) / max_len

    # --- Compare predicted vs ground truth ---

    if len(predicted_json["persons"]) != len(ground_truth_json["persons"]):
        print(f"Error: Number of persons in predicted_json ({len(predicted_json['persons'])}) does not match ground_truth_json ({len(ground_truth_json['persons'])})")
        return
    else:
        overall_total_norm_dist = 0.0
        overall_num_fields = 0

        for idx, (pred_person, gt_person) in enumerate(zip(predicted_json["persons"], ground_truth_json["persons"])):
            print(f"\n--- Person {idx+1} ---")
            person_total_norm_dist = 0.0
            num_fields = len(pred_person.keys())
            for key in pred_person.keys():
                pred_value = pred_person[key]["value"]
                gt_value = gt_person[key]["value"]
                norm_dist = normalized_edit_distance(pred_value, gt_value)
                print(f"{key}: predicted='{pred_value}' | ground_truth='{gt_value}' | normalized_edit_distance={norm_dist:.3f}")
                person_total_norm_dist += norm_dist

            overall_norm_dist = person_total_norm_dist / num_fields if num_fields > 0 else 0.0
            print(f"Overall normalized edit distance for person {idx+1}: {overall_norm_dist:.3f}")

            overall_total_norm_dist += person_total_norm_dist
            overall_num_fields += num_fields

        overall_dataset_norm_dist = overall_total_norm_dist / overall_num_fields if overall_num_fields > 0 else 0.0
        print(f"\nNormalized edit distance over all persons and fields: {overall_dataset_norm_dist:.3f}")
        return overall_dataset_norm_dist
    

def string_similarity(a, b):
    """Return a similarity between 0 and 1 for two strings (handles None)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()

def person_similarity(p1, p2, use_fuzzy=True):
    """Compare two person dicts by their .value fields."""
    fields = ['vader', 'moeder', 'geboorte_datum', 'geboorte_plaats', 'laatste_woonplaats']
    scores = []
    for field in fields:
        v1 = p1.get(field, {}).get('value')
        v2 = p2.get(field, {}).get('value')
        if use_fuzzy:
            scores.append(string_similarity(v1, v2))
        else:
            scores.append(1.0 if v1 == v2 and v1 is not None else 0.0)
        scores.append(string_similarity(v1, v2))
    return sum(scores) / len(scores)

def best_match_similarity(list1, list2):
    """Compute max similarity matching between two person lists regardless of order."""
    n = len(list1)
    m = len(list2)
    size = max(n, m)
    
    # Build similarity matrix (size x size)
    sim_matrix = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            if i < n and j < m:
                sim_matrix[i, j] = person_similarity(list1[i], list2[j])
            else:
                sim_matrix[i, j] = 0.0  # no match for extra rows
    
    # Convert to cost matrix for Hungarian algorithm (we minimize cost)
    cost_matrix = 1.0 - sim_matrix
    
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    matched_similarities = sim_matrix[row_ind, col_ind]
    return matched_similarities.mean()

