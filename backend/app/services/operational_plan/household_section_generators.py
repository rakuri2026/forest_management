from typing import Any, Dict, Optional
from app.utils.number_format import format_devanagari as fmt


def generate_household_narration(raw_data: dict) -> Optional[str]:
    """Generate Nepali summary paragraph for Household Data section."""
    hh = raw_data.get("households", {})
    if not hh.get("available"):
        return None

    total = hh.get("total_households", 0)
    pop = hh.get("total_population", 0)
    male = hh.get("total_male", 0)
    female = hh.get("total_female", 0)
    timber = hh.get("timber_demand_cft", 0)
    firewood = hh.get("firewood_demand_bhari", 0)
    forest_occ = hh.get("forest_based_occupation", 0)

    prosperity = hh.get("prosperity_distribution", {})
    caste = hh.get("caste_distribution", {})
    prosperous_count = sum(prosperity.values()) if prosperity else 0

    parts = [
        f"यस सामुदायिक वन उपभोक्ता समूहमा जम्मा {fmt(total, 0)} घरधुरी रहेका छन्।",
    ]

    if pop:
        parts.append(
            f"कुल जनसंख्या {fmt(pop, 0)} रहेको छ, "
            f"जसमा पुरुष {fmt(male, 0)} र महिला {fmt(female, 0)} रहेका छन्।"
        )

    if prosperous_count > 0:
        sorted_prosperity = sorted(prosperity.items(), key=lambda x: x[1], reverse=True)
        prosperity_desc = ", ".join(
            f"{k}: {fmt(v, 0)} घरधुरी" for k, v in sorted_prosperity
        )
        parts.append(f"समृद्धि वितरण: {prosperity_desc}।")

    if caste:
        sorted_caste = sorted(caste.items(), key=lambda x: x[1], reverse=True)
        caste_desc = ", ".join(
            f"{k}: {fmt(v, 0)} घरधुरी" for k, v in sorted_caste
        )
        parts.append(f"जातीय वर्गीकरण: {caste_desc}।")

    if forest_occ:
        parts.append(
            f"वनमा आधारित पेशा भएका घरधुरी {fmt(forest_occ, 0)} रहेका छन्।"
        )

    if timber or firewood:
        demand_parts = []
        if timber:
            demand_parts.append(f"काठ: {fmt(timber, 2)} घनफिट")
        if firewood:
            demand_parts.append(f"दाउरा: {fmt(firewood, 2)} भारी")
        parts.append(
            f"वार्षिक वन पैदावार माग: {' ,'.join(demand_parts)} रहेको छ।"
        )

    return " ".join(parts)


def generate_committee_narration(raw_data: dict) -> Optional[str]:
    """Generate Nepali summary paragraph for Forest User Committee section."""
    cm = raw_data.get("committees", {})
    uc = cm.get("user_committee", {})
    ac = cm.get("advisory_committee", {})
    fc = cm.get("financial_committee", {})
    ug = raw_data.get("user_group", {})

    uc_total = uc.get("total_members", 0)
    ac_total = ac.get("total_members", 0)
    fc_total = fc.get("total_members", 0)
    settlements = ug.get("total_settlements", 0)

    if not uc_total and not ac_total and not fc_total:
        return None

    parts = []

    if uc_total:
        uc_members = uc.get("members", [])
        women_count = sum(1 for m in uc_members if m.get("gender") == "महिला")
        men_count = sum(1 for m in uc_members if m.get("gender") == "पुरूष")

        parts.append(
            f"यस सामुदायिक वनको उपभोक्ता समितिमा जम्मा {fmt(uc_total, 0)} जना सदस्य रहेका छन्।"
        )
        if women_count or men_count:
            parts.append(
                f"जसमध्ये महिला {fmt(women_count, 0)} जना र पुरुष {fmt(men_count, 0)} जना रहेका छन्।"
            )

        positions = {}
        for m in uc_members:
            pos = m.get("position", "सदस्य")
            positions[pos] = positions.get(pos, 0) + 1
        if positions:
            pos_desc = ", ".join(f"{k}: {fmt(v, 0)}" for k, v in positions.items())
            parts.append(f"पद वितरण: {pos_desc}।")

    if ac_total:
        parts.append(f"सल्लाहकार समितिमा {fmt(ac_total, 0)} जना सदस्य रहेका छन्।")

    if fc_total:
        parts.append(f"वित्त समितिमा {fmt(fc_total, 0)} जना सदस्य रहेका छन्।")

    if settlements:
        parts.append(
            f"समूहको क्षेत्रमा {fmt(settlements, 0)} वटा बस्तीहरू रहेका छन्।"
        )

    return " ".join(parts)
