import numpy as np
from sklearn.metrics import cohen_kappa_score, confusion_matrix

from app.schemas.analysis import ModelAccuracy


def stratified_indices(
    labels: np.ndarray, train_ratio: float = 0.7, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train_rows: list[int] = []
    test_rows: list[int] = []
    for label in np.unique(labels):
        rows = np.flatnonzero(labels == label)
        rows = rng.permutation(rows)
        cut = max(1, int(round(len(rows) * train_ratio)))
        if len(rows) > 1:
            cut = min(cut, len(rows) - 1)
        train_rows.extend(rows[:cut].tolist())
        test_rows.extend(rows[cut:].tolist())
    return np.array(sorted(train_rows), dtype=np.int32), np.array(
        sorted(test_rows), dtype=np.int32
    )


def accuracy_report(
    y_true: np.ndarray, y_pred: np.ndarray, class_labels: list[str]
) -> ModelAccuracy:
    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()
    if y_true.size == 0 or y_true.size != y_pred.size:
        return ModelAccuracy(
            overall_accuracy=0.0,
            kappa=0.0,
            confusion_matrix=[],
            class_names=class_labels,
            samples=0,
        )

    matrix = confusion_matrix(
        y_true.tolist(), y_pred.tolist(), labels=list(range(len(class_labels)))
    )
    total = int(matrix.sum())
    correct = int(np.trace(matrix))
    kappa_value = cohen_kappa_score(y_true.tolist(), y_pred.tolist())
    if not np.isfinite(kappa_value):
        kappa_value = 0.0

    return ModelAccuracy(
        overall_accuracy=round(correct / total, 4) if total else 0.0,
        kappa=round(float(kappa_value), 4),
        confusion_matrix=[[int(v) for v in row] for row in matrix],
        class_names=class_labels,
        samples=total,
    )


def per_class_user_accuracy(report: ModelAccuracy) -> list[dict]:
    rows: list[dict] = []
    matrix = np.array(report.confusion_matrix, dtype=np.float64)
    for idx, name in enumerate(report.class_names):
        if matrix.size == 0 or idx >= matrix.shape[0]:
            continue
        reference = float(matrix[idx].sum())
        produced = float(matrix[:, idx].sum())
        hit = float(matrix[idx, idx])
        rows.append(
            {
                "class": name,
                "reference_pixels": int(reference),
                "produced_pixels": int(produced),
                "user_accuracy": round(hit / reference, 4) if reference else 0.0,
                "producer_accuracy": round(hit / produced, 4) if produced else 0.0,
            }
        )
    return rows
