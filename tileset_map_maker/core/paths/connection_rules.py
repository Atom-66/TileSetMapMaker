from typing import Dict, List, Tuple

from .models import (
    EDGE_DIRECTIONS,
    OPPOSITE_EDGE,
    CompatibilityResult,
    EdgeSignature,
    PathVariant,
)


def _strip_continuity(
    strip_a: Tuple[Tuple[int, int, int, int], ...],
    strip_b: Tuple[Tuple[int, int, int, int], ...],
) -> float:
    """Computes bin-by-bin RGBA continuity (0.0..1.0) across two edge strips."""
    if not strip_a or not strip_b:
        return 0.5
    n = min(len(strip_a), len(strip_b))
    diff_sum = 0.0
    for i in range(n):
        ra, ga, ba, aa = strip_a[i]
        rb, gb, bb, ab = strip_b[i]
        diff_sum += (abs(ra - rb) + abs(ga - gb) + abs(ba - bb) + abs(aa - ab)) / (4.0 * 255.0)
    return max(0.0, 1.0 - diff_sum / float(max(1, n)))


def _span_overlap_ratio(span_a: Tuple[int, int], span_b: Tuple[int, int]) -> float:
    a0, a1 = span_a
    b0, b1 = span_b
    len_a = max(0, a1 - a0)
    len_b = max(0, b1 - b0)
    if len_a == 0 and len_b == 0:
        return 1.0
    if len_a == 0 or len_b == 0:
        return 0.0
    inter = max(0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return inter / float(max(1, union))


class ConnectionRuleEngine:
    """
    Evaluates directional graphical compatibility between PathVariants.
    Combines:
      1. Explicit user-defined directional compatibility rules (highest priority)
      2. Role & decorative-element guards (decorations never bridge path edges)
      3. Edge contour type compatibility (open_path <-> open_path, closed <-> closed)
      4. Navigable surface width & span alignment (prevents sudden width pinching)
      5. Texture activity & 8-bin pixel strip continuity (never color-only!)
    """

    COMPATIBLE_EDGE_PAIRS = {
        ("open_full", "open_full"): 1.0,
        ("open_full", "open_path"): 0.78,
        ("open_path", "open_full"): 0.78,
        ("open_path", "open_path"): 1.0,
        ("closed_outer", "closed_outer"): 0.95,
        ("closed_transparent", "closed_transparent"): 0.95,
        ("mixed", "open_path"): 0.70,
        ("open_path", "mixed"): 0.70,
        ("mixed", "mixed"): 0.72,
    }

    @classmethod
    def check_edge_compatibility(
        cls,
        var_a: PathVariant,
        var_b: PathVariant,
        direction: str,
        threshold: float = 0.55,
    ) -> CompatibilityResult:
        """
        Checks whether var_b can be placed immediately adjacent to var_a in
        direction ('N', 'E', 'S', 'W').
        """
        if direction not in EDGE_DIRECTIONS:
            return CompatibilityResult(False, 0.0, ["Nieprawidłowy kierunek"])

        # 1. Decorative elements must never be used to bridge path connections
        if not var_a.allow_connections or not var_b.allow_connections:
            return CompatibilityResult(False, 0.0, ["Element dekoracyjny nie łączy ścieżek"])

        # 2. Explicit manual rules take priority when defined
        explicit_a = var_a.compatible_neighbors.get(direction)
        opp = OPPOSITE_EDGE[direction]
        explicit_b = var_b.compatible_neighbors.get(opp)
        if explicit_a is not None and len(explicit_a) > 0:
            if var_b.id in explicit_a or var_b.role in explicit_a:
                return CompatibilityResult(True, 1.0, ["Jawna reguła kompatybilności użytkownika"])
            return CompatibilityResult(False, 0.0, ["Wykluczone przez jawną regułę kompatybilności"])
        if explicit_b is not None and len(explicit_b) > 0:
            if var_a.id in explicit_b or var_a.role in explicit_b:
                return CompatibilityResult(True, 1.0, ["Jawna reguła kompatybilności sąsiada"])
            return CompatibilityResult(False, 0.0, ["Wykluczone przez regułę sąsiada"])

        # 3. Structural pixel-edge signature comparison
        edge_a: EdgeSignature = var_a.edges.get(direction)
        edge_b: EdgeSignature = var_b.edges.get(opp)
        if edge_a is None or edge_b is None:
            # Fallback when edges were not analyzed yet: compare surface width & role sanity
            if var_a.surface_width_px > 0 and var_b.surface_width_px > 0:
                ratio = min(var_a.surface_width_px, var_b.surface_width_px) / float(
                    max(var_a.surface_width_px, var_b.surface_width_px)
                )
                return CompatibilityResult(
                    ratio >= 0.65,
                    ratio,
                    [f"Porównanie szerokości nawierzchni ({var_a.surface_width_px}px vs {var_b.surface_width_px}px)"],
                )
            return CompatibilityResult(True, 0.75, ["Domyślna kompatybilność (brak podpisów krawędzi)"])

        reasons: List[str] = []

        # 3a. Edge contour class match (prevents open path slamming into closed wall!)
        pair_score = cls.COMPATIBLE_EDGE_PAIRS.get((edge_a.edge_type, edge_b.edge_type), 0.15)
        if pair_score < 0.5:
            reasons.append(f"Niezgodny typ krawędzi ({edge_a.edge_type} ↔ {edge_b.edge_type})")
            return CompatibilityResult(False, pair_score, reasons)

        # 3b. Real visible navigable surface width & lateral contour alignment
        surface_pinched = False
        if edge_a.has_surface and edge_b.has_surface:
            span_score = _span_overlap_ratio(edge_a.surface_span, edge_b.surface_span)
            w_min = min(edge_a.surface_width_px, edge_b.surface_width_px)
            w_max = max(1, edge_a.surface_width_px, edge_b.surface_width_px)
            w_ratio = w_min / float(w_max)
            width_score = 0.55 * span_score + 0.45 * w_ratio
            if w_ratio < 0.72 or span_score < 0.62:
                surface_pinched = True
                reasons.append(
                    f"Wykryto przewężenie lub przesunięcie konturu nawierzchni "
                    f"({edge_a.surface_width_px}px vs {edge_b.surface_width_px}px, "
                    f"pokrycie konturu {int(span_score * 100)}%)"
                )
            elif width_score < 0.65:
                reasons.append(
                    f"Niezgodność szerokości przejścia ({edge_a.surface_width_px}px vs {edge_b.surface_width_px}px)"
                )
        else:
            width_score = 1.0

        # 3c. Texture activity continuity (flat surface vs richly textured surface)
        tex_diff = abs(edge_a.texture_activity - edge_b.texture_activity)
        tex_score = max(0.0, 1.0 - tex_diff * 5.0)
        if tex_score < 0.60:
            reasons.append("Różnica faktury/detali na granicy kafelków")

        # 3d. 8-bin pixel strip continuity across actual seam
        strip_score = _strip_continuity(edge_a.sample_strip, edge_b.sample_strip)

        total = 0.25 * pair_score + 0.35 * width_score + 0.15 * tex_score + 0.25 * strip_score
        compatible = (not surface_pinched) and total >= threshold and width_score >= 0.58
        if compatible and not reasons:
            reasons.append(f"Zgodne krawędzie i szerokość nawierzchni ({int(total * 100)}%)")
        return CompatibilityResult(compatible, round(total, 4), reasons)

    @classmethod
    def validate_intersection_composition(
        cls,
        center_var: PathVariant,
        arm_variants: Dict[str, PathVariant],
        threshold: float = 0.55,
    ) -> CompatibilityResult:
        """
        Validates an intersection (4-way cross or T-junction) as ONE coherent
        logical composition across all present cardinal arms ('N', 'E', 'S', 'W')
        simultaneously:
        - Every single present junction boundary must pass check_edge_compatibility
          (never accepts 3 good arms + 1 pinched arm!).
        - When opposite arms (W vs E, or N vs S) have symmetric source surface
          widths (diff <= 2px), validates that the center tile provides matching
          opening widths on both opposite sides (without forcing symmetry on
          intentionally asymmetric arm pairs!).
        """
        if not arm_variants:
            return CompatibilityResult(True, 1.0, ["Brak sąsiednich odnóg do walidacji"])

        reasons: List[str] = []
        scores: List[float] = []
        all_ok = True

        for direction, arm_var in arm_variants.items():
            if direction not in EDGE_DIRECTIONS:
                continue
            res = cls.check_edge_compatibility(center_var, arm_var, direction, threshold=threshold)
            scores.append(res.score)
            if not res.compatible:
                all_ok = False
                reasons.append(f"Odnoga {direction}: {'; '.join(res.reasons)}")

        # Opposite-arm symmetry check (only when the incoming arms themselves are symmetric!)
        for dir_a, dir_b in (("W", "E"), ("N", "S")):
            if dir_a in arm_variants and dir_b in arm_variants:
                opp_a = OPPOSITE_EDGE[dir_a]
                opp_b = OPPOSITE_EDGE[dir_b]
                arm_ea = arm_variants[dir_a].edges.get(opp_a)
                arm_eb = arm_variants[dir_b].edges.get(opp_b)
                ctr_ea = center_var.edges.get(dir_a)
                ctr_eb = center_var.edges.get(dir_b)
                if arm_ea and arm_eb and ctr_ea and ctr_eb and arm_ea.has_surface and arm_eb.has_surface:
                    arm_symmetric = abs(arm_ea.surface_width_px - arm_eb.surface_width_px) <= 2
                    if arm_symmetric:
                        max_c = max(1, ctr_ea.surface_width_px, ctr_eb.surface_width_px)
                        tol = max(2, int(round(max_c * 0.14)))
                        if abs(ctr_ea.surface_width_px - ctr_eb.surface_width_px) > tol:
                            all_ok = False
                            reasons.append(
                                f"Asymetria środka skrzyżowania {dir_a}/{dir_b} "
                                f"({ctr_ea.surface_width_px}px vs {ctr_eb.surface_width_px}px) "
                                f"przy symetrycznych odnogach"
                            )

        mean_score = sum(scores) / float(len(scores)) if scores else 0.0
        if all_ok and not reasons:
            reasons.append(
                f"Spójna kompozycja skrzyżowania na wszystkich {len(scores)} odnogach ({int(mean_score * 100)}%)"
            )
        return CompatibilityResult(all_ok, round(mean_score if all_ok else min(mean_score, 0.40), 4), reasons)

    @classmethod
    def suggest_compatibility_matrix(
        cls,
        variants: List[PathVariant],
        threshold: float = 0.58,
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Automatically computes suggested directional compatibility lists
        {variant_id: {"N": [...], "E": [...], "S": [...], "W": [...]}}
        for a set of variants so users can review or refine them.
        """
        matrix: Dict[str, Dict[str, List[str]]] = {}
        for va in variants:
            matrix[va.id] = {d: [] for d in EDGE_DIRECTIONS}
            if not va.allow_connections:
                continue
            for d in EDGE_DIRECTIONS:
                for vb in variants:
                    if not vb.allow_connections:
                        continue
                    res = cls.check_edge_compatibility(va, vb, d, threshold=threshold)
                    if res.compatible:
                        matrix[va.id][d].append(vb.id)
        return matrix
