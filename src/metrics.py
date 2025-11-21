import json
import distance  
from difflib import SequenceMatcher
import numpy as np
from scipy.optimize import linear_sum_assignment
import distance
from apted import APTED, Config
from apted.helpers import Tree
from lxml import etree, html
from collections import deque
from utils import load_cells


class TableTree(Tree):
    def __init__(self, tag, colspan=None, rowspan=None, content=None, *children):
        self.tag = tag
        self.colspan = colspan
        self.rowspan = rowspan
        self.content = content
        self.children = list(children)

    def bracket(self):
        """Show tree using brackets notation"""
        if self.tag == 'td':
            result = '"tag": %s, "colspan": %d, "rowspan": %d, "text": %s' % \
                     (self.tag, self.colspan, self.rowspan, self.content)
        else:
            result = '"tag": %s' % self.tag
        for child in self.children:
            result += child.bracket()
        return "{{{}}}".format(result)


class CustomConfig(Config):
    @staticmethod
    def maximum(*sequences):
        """Get maximum possible value
        """
        return max(map(len, sequences))

    def normalized_distance(self, *sequences):
        """Get distance from 0 to 1
        """
        return float(distance.levenshtein(*sequences)) / self.maximum(*sequences)

    def rename(self, node1, node2):
        """Compares attributes of trees"""
        if (node1.tag != node2.tag) or (node1.colspan != node2.colspan) or (node1.rowspan != node2.rowspan):
            return 1.
        if node1.tag == 'td':
            if node1.content or node2.content:
                return self.normalized_distance(node1.content, node2.content)
        return 0.


class TEDS(object):
    ''' Tree Edit Distance basead Similarity
    '''

    def __init__(self, structure_only=False, n_jobs=1, ignore_nodes=None):
        assert isinstance(n_jobs, int) and (n_jobs >= 1), 'n_jobs must be an integer greather than 1'
        self.structure_only = structure_only
        self.n_jobs = n_jobs
        self.ignore_nodes = ignore_nodes
        self.__tokens__ = []

    def tokenize(self, node):
        ''' Tokenizes table cells
        '''
        self.__tokens__.append('<%s>' % node.tag)
        if node.text is not None:
            self.__tokens__ += list(node.text)
        for n in node.getchildren():
            self.tokenize(n)
        if node.tag != 'unk':
            self.__tokens__.append('</%s>' % node.tag)
        if node.tag != 'td' and node.tail is not None:
            self.__tokens__ += list(node.tail)

    def load_html_tree(self, node, parent=None):
        ''' Converts HTML tree to the format required by apted
        '''
        global __tokens__
        if node.tag == 'td':
            if self.structure_only:
                cell = []
            else:
                self.__tokens__ = []
                self.tokenize(node)
                cell = self.__tokens__[1:-1].copy()
            new_node = TableTree(node.tag,
                                 int(node.attrib.get('colspan', '1')),
                                 int(node.attrib.get('rowspan', '1')),
                                 cell, *deque())
        else:
            new_node = TableTree(node.tag, None, None, None, *deque())
        if parent is not None:
            parent.children.append(new_node)
        if node.tag != 'td':
            for n in node.getchildren():
                self.load_html_tree(n, new_node)
        if parent is None:
            return new_node

    def evaluate(self, pred, true):
        ''' Computes TEDS score between the prediction and the ground truth of a
            given sample
        '''
        if (not pred) or (not true):
            return 0.0
        parser = html.HTMLParser(remove_comments=True, encoding='utf-8')
        pred = html.fromstring(pred, parser=parser)
        true = html.fromstring(true, parser=parser)
        if pred.xpath('//table') and true.xpath('//table'):
            pred = pred.xpath('//table')[0]
            true = true.xpath('//table')[0]
            if self.ignore_nodes:
                etree.strip_tags(pred, *self.ignore_nodes)
                etree.strip_tags(true, *self.ignore_nodes)
            n_nodes_pred = len(pred.xpath(".//*"))
            n_nodes_true = len(true.xpath(".//*"))
            n_nodes = max(n_nodes_pred, n_nodes_true)
            tree_pred = self.load_html_tree(pred)
            tree_true = self.load_html_tree(true)
            distance = APTED(tree_pred, tree_true, CustomConfig()).compute_edit_distance()
            return 1.0 - (float(distance) / n_nodes)
        else:
            return 0.0


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


import numpy as np
import distance
from scipy.optimize import linear_sum_assignment

def normalized_edit_distance(a, b):
    """Compute normalized Levenshtein distance (0–1)."""
    if not a or not b:
        return 1.0  # completely dissimilar if one is empty
    return distance.levenshtein(a.strip().lower(), b.strip().lower()) / max(len(a), len(b))

def person_similarity(p1, p2):
    """Compute average similarity between two persons (for matching)."""
    fields = [f for f in p2.keys() if 'value' in p2[f]]
    sims = []
    for field in fields:
        v1 = p1.get(field, {}).get('value')
        v2 = p2.get(field, {}).get('value')
        if v1 or v2:
            d = normalized_edit_distance(v1 or "", v2 or "")
            sims.append(1 - d)
    return np.mean(sims) if sims else 0.0


def infomration_extraction_precision_recall(list_pred, list_gt, threshold=0.4):
    """Compute overall precision and recall for best-matched persons."""
    if not list_pred or not list_gt:
        return 0.0, 0.0

    n, m = len(list_pred), len(list_gt)
    size = max(n, m)

    # --- Step 1: Build similarity matrix for matching ---
    sim_matrix = np.zeros((size, size))
    for i in range(n):
        for j in range(m):
            sim_matrix[i, j] = person_similarity(list_pred[i], list_gt[j])

    # --- Step 2: Find best match (Hungarian algorithm) ---
    cost_matrix = 1.0 - sim_matrix
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    total_precision = 0.0
    total_recall = 0.0

    for i, j in zip(row_ind, col_ind):
        if i >= n or j >= m:
            continue

        person_pred = list_pred[i]
        person_gt = list_gt[j]
        pred_fields = [f for f in person_pred.keys() if 'value' in person_pred[f]]
        gt_fields = [f for f in person_gt.keys() if 'value' in person_gt[f]]

        # --- Count correct matches (field-wise) ---
        correct_for_precision = 0
        correct_for_recall = 0

        for field in pred_fields:
            v1 = person_pred[field].get('value')
            v2 = person_gt.get(field, {}).get('value')
            d = 1.0 if (v1 is None or v2 is None) else normalized_edit_distance(v1 or "null", v2 or "null")
            if d < threshold:
                correct_for_precision += 1
        for field in gt_fields:
            v1 = person_pred.get(field, {}).get('value')
            v2 = person_gt[field].get('value')
            d = 1.0 if (v1 is None or v2 is None) else normalized_edit_distance(v1 or "null", v2 or "null")
            if d < threshold:
                correct_for_recall += 1

        person_precision = correct_for_precision / len(pred_fields) if pred_fields else 0
        person_recall = correct_for_recall / len(gt_fields) if gt_fields else 0

        total_precision += person_precision
        total_recall += person_recall

    # --- Step 3: Macro-averaged Precision and Recall ---
    overall_precision = total_precision / len(list_pred)
    overall_recall = total_recall / len(list_gt)

    return round(overall_precision, 4), round(overall_recall, 4)

def iou(poly1, poly2):
    """Compute IoU between two polygons."""
    inter = poly1.intersection(poly2).area
    union = poly1.union(poly2).area
    return inter / union if union > 0 else 0.0

def precision_recall_for_thresholds(gt_cells, pred_cells, iou_thresholds):
    """Compute precision and recall per class over multiple IoU thresholds."""
    results = {}
    for key, gt_poly in gt_cells.items():
        pred_poly = pred_cells.get(key)
        if pred_poly is None:
            # no prediction for this cell
            results[key] = {
                "precision": [0.0] * len(iou_thresholds),
                "recall": [0.0] * len(iou_thresholds),
            }
            continue

        iou_score = iou(gt_poly, pred_poly)
        precisions = []
        recalls = []

        for thr in iou_thresholds:
            match = iou_score >= thr
            precisions.append(1.0 if match else 0.0)
            recalls.append(1.0 if match else 0.0)

        results[key] = {
            "precision": precisions,
            "recall": recalls,
        }

    return results

def compute_mAP(gt_file, pred_file, thresholds=np.arange(0.5, 1.0, 0.05)):
    gt_cells = load_cells(gt_file)
    pred_cells = load_cells(pred_file)

    results = precision_recall_for_thresholds(gt_cells, pred_cells, thresholds)

    aps = []
    for key, vals in results.items():
        # Average precision per class = mean over thresholds
        ap = np.mean(vals["precision"])  # recall same since 1 GT per class
        aps.append(ap)

    mean_ap = np.mean(aps) if aps else 0.0

    # print("Per-class average precision:")
    # for key, vals in results.items():
    #     print(
    #         f"  Cell {key}: AP={np.mean(vals['precision']):.3f}, "
    #         f"Mean IoU-based recall={np.mean(vals['recall']):.3f}"
    #     )

    print(f"\nFinal Mean Average Precision (mAP): {mean_ap:.4f}")
    return mean_ap