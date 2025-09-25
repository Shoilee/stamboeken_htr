import json
import distance  # pip install Distance

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