import json
import os
from pathlib import Path
from src.metrics import infomration_extraction_precision_recall


def count_provenance_and_total(json_path):
    """
    Reads the JSON file and counts:
    1. Number of attributes with cell-level provenance (cell != null)
    2. Total number of attributes in the persons list
    """

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    persons = data.get("persons", [])

    cell_provenance_count = 0
    total_attributes = 0

    for person in persons:
        for attr_name, attr_value in person.items():
            
            # Case 1: Nested attributes: person["name"]["basesurname"], etc.
            if isinstance(attr_value, dict) and "value" not in attr_value:
                # Example: "name" → {"basesurname": {...}, "firstnames": {...}}
                for subattr_name, subattr in attr_value.items():
                    total_attributes += 1
                    if subattr.get("cell") is not None:
                        cell_provenance_count += 1

            # Case 2: Normal attributes: person["birth_place"], etc.
            else:
                total_attributes += 1
                if attr_value.get("cell") is not None:
                    cell_provenance_count += 1
    
    provenance_ratio = round((cell_provenance_count / total_attributes) * 100, 2) if total_attributes else 0.0

    return cell_provenance_count, total_attributes, provenance_ratio

def has_provenance(field):
    return field.get("cell") is not None or field.get("original_spans") not in [None, [], ""]


# -------------------------------------
# Filter one person: keep only provenance
# -------------------------------------
def filter_person(person):
    filtered_person = {}

    for attr_name, attr_value in person.items():

        # Case 1: nested attributes (e.g., "name": {...})
        if isinstance(attr_value, dict) and "value" not in attr_value:
            nested_filtered = {}

            for sub_attr_name, sub_attr_value in attr_value.items():
                if has_provenance(sub_attr_value):
                    nested_filtered[sub_attr_name] = sub_attr_value

            if nested_filtered:  # keep only if at least one survives
                filtered_person[attr_name] = nested_filtered

        # Case 2: flat attributes with value/row/cell/spans
        else:
            if has_provenance(attr_value):
                filtered_person[attr_name] = attr_value

    return filtered_person


# -------------------------------------------------------------
# Main: load JSON, filter all predicted persons, compute metrics
# -------------------------------------------------------------
def evaluate_after_provenance_filter(json_pred_path, json_gt_path):
    """
    Reads prediction JSON and ground-truth JSON.
    Filters predictions by provenance.
    Computes precision, recall, F1 using your existing function.
    """

    # --- Load prediction JSON ---
    with open(json_pred_path, "r", encoding="utf-8") as f:
        pred_json = json.load(f)

    # --- Load ground truth JSON ---
    with open(json_gt_path, "r", encoding="utf-8") as f:
        gt_json = json.load(f)

    list_pred_raw = pred_json.get("persons", [])
    list_gt       = gt_json.get("persons", [])

    # --- Filter predicted persons ---
    list_pred_filtered = [filter_person(p) for p in list_pred_raw]

    # --- Compute precision, recall, F1 ---
    precision, recall, f1 = infomration_extraction_precision_recall(
        list_pred_filtered,
        list_gt,
        threshold=0.4
    )

    # print("Precision:", precision)
    # print("Recall:", recall)
    # print("F1-score:", f1)

    return precision, recall, f1


def main(directory_path):
    """
    Process all JSON files in a folder and compute average metrics.
    """
    json_files = list(Path(directory_path).glob("*.json"))
    
    all_results = []
    
    for json_file_path in json_files:
        try:
            # Count provenance
            cell_count, total_count, ratio = count_provenance_and_total(str(json_file_path))
            
            # Evaluate metrics (assuming corresponding GT file exists)
            gt_path = os.path.join("data/labels/info", json_file_path.name.replace('.jpg', ''))
            
            if os.path.exists(gt_path):
                precision, recall, f1 = evaluate_after_provenance_filter(str(json_file_path), gt_path)
                all_results.append({
                    "file": json_file_path.name,
                    "cell_count": cell_count,
                    "total_count": total_count,
                    "provenance_ratio": ratio,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1
                })
        except Exception as e:
            print(f"Error processing {json_file_path.name}: {e}")
    
    # Compute averages
    if all_results:
        avg_cell_count = sum(r["cell_count"] for r in all_results) / len(all_results)
        avg_total_count = sum(r["total_count"] for r in all_results) / len(all_results)
        avg_provenance_ratio = sum(r["provenance_ratio"] for r in all_results) / len(all_results)
        avg_precision = sum(r["precision"] for r in all_results) / len(all_results)
        avg_recall = sum(r["recall"] for r in all_results) / len(all_results)
        avg_f1 = sum(r["f1"] for r in all_results) / len(all_results)
        
        print(f"\nAverages across {len(all_results)} files:")
        print(f"Avg Cell Count: {avg_cell_count:.2f}")
        print(f"Avg Total Count: {avg_total_count:.2f}")
        print(f"Avg Provenance Ratio: {avg_provenance_ratio:.2f}%")
        print(f"Avg Precision: {avg_precision:.4f}")
        print(f"Avg Recall: {avg_recall:.4f}")
        print(f"Avg F1: {avg_f1:.4f}")
        
        return all_results

if __name__ == "__main__":
    folder = "data/json"
    main(folder)


