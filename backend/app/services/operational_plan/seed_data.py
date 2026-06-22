from typing import List
from .tree_models import TreeNode


def _node(
    type: str,
    title_ne: str,
    title_en: str = "",
    content: str = "",
    is_locked: bool = False,
    children: list = None,
    content_type: str = "richtext",
    **kwargs,
) -> TreeNode:
    return TreeNode(
        type=type,
        title_ne=title_ne,
        title_en=title_en or title_ne,
        content=content,
        is_locked=is_locked,
        children=children or [],
        content_type=content_type,
        **kwargs,
    )


def get_default_seed_tree() -> List[TreeNode]:
    return [
        # ── Preamble / TOC Items ──
        _node("preamble", "कबुलियतनामा", "Kabuliyatnama",
              "यस सामुदायिक वनको नाम {{forest_name}} हो। यो {{district}} जिल्लाको {{municipality}} मा अवस्थित छ।"),
        _node("preamble", "शब्दावली परिचय", "Glossary",
              "यस कार्ययोजनामा प्रयोग गरिएका मुख्य शब्दहरूको परिभाषा:"),
        _node("preamble", "वन कार्ययोजना स्वीकृति", "Approval",
              "यो कार्ययोजना {{prepared_by}} द्वारा तयार गरी {{reviewed_by}} द्वारा समीक्षा गरिएको हो।"),
        _node("preamble", "प्रस्तावना", "Preface",
              "{{forest_name}} सामुदायिक वन उपभोक्ता समूहको यो व्यवस्थापन कार्ययोजना {{plan_year_start}} देखि {{plan_year_end}} सम्मको लागि तयार गरिएको हो।"),
        _node("preamble", "कार्ययोजनाको सारांश", "Summary",
              "यस सामुदायिक वनको कुल क्षेत्रफल {{total_area_hectares}} हेक्टर रहेको छ। यसमा {{blocks_count}} वटा ब्लक रहेका छन्।"),

        # ── Section १: परिचय ──
        _node("section", "परिचय", "Introduction",
              "{{forest_name}} सामुदायिक वन {{district}} जिल्लाको {{municipality}} वडा नं. {{ward}} मा अवस्थित छ।",
              children=[
                  _node("subsection", "संक्षिप्त नाम र प्रारम्भ", "Short Name and Commencement",
                        "यस कार्ययोजनालाई \"{{forest_name}} सामुदायिक वन व्यवस्थापन कार्ययोजना\" भनिनेछ।"),
                  _node("subsection", "परिभाषा", "Definitions",
                        "यस कार्ययोजनामा प्रयोग गरिएका शब्दहरूको परिभाषा:"),
              ]),

        # ── Section २: भौगोलिक अवस्थिति ──
        _node("section", "सामुदायिक वन र समूहको भौगोलिक अवस्थिति", "Geography",
              "यस वनको भौगोलिक अवस्थिति निम्नानुसार छ:",
              children=[
                  _node("subsection", "समूहको परिचय", "Group Introduction",
                        "{{user_group_name}} उपभोक्ता समूहको दर्ता नं. {{user_group_code}} रहेको छ।"),
                  _node("subsection", "वनको भौगोलिक अवस्था", "Geographic Condition",
                        "यस वनको उचाई {{altitude_min_m}} देखि {{altitude_max_m}} मिटर सम्म रहेको छ। औसत उचाई {{altitude_mean_m}} मिटर छ।"),
                  _node("subsection", "वनको ऐतिहासिक पृष्ठभूमि", "Historical Background",
                        "{{forest_name}} सामुदायिक वनको स्थापना मिति {{cf_handover_date}} हो।"),
                  _node("subsection", "सिमाना (चारकिल्ला)", "Boundary",
                        "यस वनको सिमाना: पूर्व {{boundary_features_east}}, पश्चिम {{boundary_features_south}}, उत्तर {{boundary_features_north}}, दक्षिण {{boundary_features_south}}।"),
                  _node("subsection", "क्षेत्रफल र नक्सा", "Area and Map",
                        "कुल क्षेत्रफल {{total_area_hectares}} हेक्टर। प्रभावकारी क्षेत्रफल {{effective_area_hectares}} हेक्टर।\n\n"
                        "{{fieldbook_narration}}\n\n"
                        "{{fieldbook_block_summary}}\n\n"
                        "{{fieldbook_points}}\n\n"
                        "{{map:fieldbook}}"),
                  _node("subsection", "भू-उपयोग", "Land Use",
                        "{{landcover_dominant}} मुख्य भू-उपयोग प्रकार हो।"),
              ]),

        # ── Section ३: वनको किसिम र मुख्य प्रजाती ──
        _node("section", "वनको किसिम र मुख्य प्रजाती", "Forest Types and Species",
              "यस वनमा क्षेत्र सर्वेक्षण (Field Inventory) तथा रूख गणना (Tree Mapping) को आधारमा "
              "जम्मा {{total_species}} प्रजातिका रूखहरू पाइएका छन्। ती मध्ये केही मुख्य प्रजातीहरू "
              "यस खण्डमा वर्णन गरिएको छ।",
              children=[
                  # ── ३.१: वन श्रोत मापन विधी ──
                  _node("subsection", "वन श्रोत मापन विधी", "Measurement Method",
                        "वन श्रोत मापन {{sampling_type}} विधिबाट गरिएको थियो। "
                        "कुल {{sampling_total_points}} वटा नमूना प्लट राखिएका थिए। "
                        "अनुरोध गरिएको नमूना इन्टेन्सिटी {{sampling_requested_intensity}}% र "
                        "वास्तविक इन्टेन्सिटी {{sampling_actual_intensity}}% रहेको छ। "
                        "पोल (Pole) को लागि १०० वर्गमिटर र रूख (Tree) को लागि ५०० वर्गमिटर "
                        "क्षेत्रफलको नमूना प्लट प्रयोग गरिएको थियो।\n\n"
                        "ब्लक अनुसार नमुनाप्लट विवरण तलको तालिकामा प्रस्तुत गरिएको छ:\n\n"
                        "{{sampling_block_summary}}\n\n"
                        "नमुना प्लटहरूको स्थान विवरण तलको तालिकामा प्रस्तुत गरिएको छ:\n\n"
                        "{{sampling_point_locations}}\n\n"
                        "{{map:sampling_plot}}\n\n"
                        "{{map:sampling_plot_topo}}\n\n"
                        "{{map:sampling_plot_satellite}}"),

                  # ── ३.२: वनको किसिम ──
                  _node("subsection", "वनको किसिम", "Forest Type",
                        "यस वनको मुख्य वन प्रकार {{forest_type_dominant}} हो। "
                        "उपग्रह तथ्यांक विश्लेषणको आधारमा वन क्षेत्रलाई विभिन्न प्रकारमा "
                        "वर्गीकरण गरिएको छ। तलको पाई चार्टले वन प्रकारको वितरण देखाउँदछ।\n\n"
                        "{{chart:forest_type_pie}}\n\n"
                        "{{map:forest_type}}"),

                  # ── ३.३: मुख्य प्रजातीहरूको विवरण ──
                  _node("subsection", "मुख्य प्रजातीहरूको विवरण", "Main Species Description",
                        "क्षेत्र सर्वेक्षण (Field Inventory) तथा रूख गणना (Tree Mapping) को "
                        "आधारमा यस वनमा पाइने प्रमुख प्रजातीहरूको विवरण निम्नानुसार छ:\n\n"

                        "क. मुख्य प्रजाती (Dominant Species):\n"
                        "जम्मा आयतनको २०% भन्दा बढी हिस्सा ओगटेका प्रजातीहरूलाई मुख्य प्रजातीको "
                        "रूपमा वर्गीकरण गरिएको छ। यस वनमा {{fi_dominant_species}} प्रजातीहरू "
                        "मुख्य प्रजातीको रूपमा रहेका छन्। यी प्रजातीहरूको वनमा सबैभन्दा "
                        "बढी वन मौज्दात रहेको छ।\n\n"

                        "ख. सह-मुख्य प्रजाती (Co-dominant Species):\n"
                        "जम्मा आयतनको १०% देखि २०% सम्म हिस्सा ओगटेका प्रजातीहरूलाई सह-मुख्य "
                        "प्रजातीको रूपमा वर्गीकरण गरिएको छ। {{fi_co_dominant_species}} "
                        "प्रजातीहरू यस वर्गमा पर्दछन्।\n\n"

                        "ग. आनुषंगिक प्रजाती (Associated Species):\n"
                        "जम्मा आयतनको १०% भन्दा कम हिस्सा ओगटेका प्रजातीहरूलाई आनुषंगिक "
                        "प्रजातीको रूपमा वर्गीकरण गरिएको छ। {{fi_associated_species}} लगायत "
                        "अन्य प्रजातीहरू यस वर्गमा पर्दछन्।\n\n"

                        "घ. वृद्धि दर अनुसार वर्गीकरण:\n"
                        "द्रुत बृद्धि हुने प्रजातीहरू: {{fi_fast_growing_species}}\n"
                        "मध्यम बृद्धि हुने प्रजातीहरू: {{fi_moderate_growing_species}}\n"
                        "सुस्त बृद्धि हुने प्रजातीहरू: {{fi_slow_growing_species}}\n\n"

                        "तलको पाई चार्टले प्रजाती संरचना (Species Composition) देखाउँदछ:\n\n"
                        "{{chart:species_composition_pie_fi}}"),

                  # ── ३.४: ब्यास वर्ग अनुसार वन मौज्दात ──
                  _node("subsection", "ब्यास वर्ग अनुसार वन मौज्दात", "DBH Class Growing Stock",
                        "ब्लक अनुसार ब्यास वर्गको वन मौज्दात निम्नानुसार छ। यस तालिकाले "
                        "प्रति हेक्टर रूख संख्या, काठ आयतन, दाउरा आयतन र जम्मा आयतन "
                        "देखाउँदछ:\n\n"
                        "{{fi_block_dbh_class_growing_stock_np}}"),

                  # ── ३.५: ब्लक अनुसार प्रजाति वन मौज्दात ──
                  _node("subsection", "ब्लक अनुसार प्रजाति वन मौज्दात",
                        "Block-wise Species Growing Stock",
                        "ब्लक अनुसार प्रजाति स्तरको वन मौज्दात तलको तालिकामा प्रस्तुत "
                        "गरिएको छ। यस तालिकाले प्रत्येक ब्लकमा प्रजाति अनुसार प्रति "
                        "हेक्टर रूख संख्या, काठ आयतन (घ.मी./हे.), दाउरा आयतन "
                        "(घ.मी./हे.) र जम्मा आयतन (घ.मी./हे.) देखाउँदछ:\n\n"
                        "{{fi_species_block_growing_stock}}"),

                  # ── ३.६: वार्षिक उत्पादन ──
                  _node("subsection", "वार्षिक उत्पादन", "Annual Production",
                        "यस वनको औसत वार्षिक बृद्धि (MAI) {{fi_mai_percent}}% रहेको छ। "
                        "वार्षिक उत्पादन {{annual_increment_m3}} घनमिटर रहेको छ। "
                        "ब्लक अनुसारको वार्षिक बृद्धि विवरण तलको तालिकामा प्रस्तुत "
                        "गरिएको छ:\n\n"
                        "{{fi_mai_table}}"),
              ]),

        # ── Section ४: माग र अपूर्ती ──
        _node("section", "वन पैदावरको माग र अपुर्तीको अवस्था", "Demand and Supply",
              "समूहका {{hh_total_households}} घरधुरीहरूको वन पैदावर माग निम्नानुसार छ:",
              children=[
                  _node("subsection", "माग र आपूर्ति आँकलन", "Assessment Method",
                        "घरधुरी सर्वेक्षणका आधारमा माग आँकलन गरिएको हो।"),
                  _node("subsection", "माग तथा आपूर्तिको अवस्था", "Demand and Supply Status",
                        "काठको माग: {{hh_timber_demand_cft}} घनफिट। दाउराको माग: {{hh_firewood_demand_bhari}} भारी।"),
              ]),

        # ── Section ५: आर्थिक तथा सामाजिक अवस्था ──
        _node("section", "समूहको आर्थिक तथा सामाजिक अवस्था", "Socio-economic Status",
              "यस समूहमा {{hh_total_households}} घरधुरी र {{hh_total_population}} जनसंख्या रहेको छ।",
              children=[
                  _node("subsection", "सामाजिक र आर्थिक अवस्था", "Social and Economic Status",
                        "पुरूष: {{hh_total_male}}, महिला: {{hh_total_female}}। वनमा आधारित पेशा: {{hh_forest_based_occupation}} घरधुरी।"),
              ]),

        # ── Section ६: विगत समीक्षा ──
        _node("section", "विगतका वन व्यवस्थापन कार्ययोजनाको समीक्षा", "Previous Plan Review",
              "विगतका कार्ययोजनाको समीक्षा निम्नानुसार गरिएको छ:",
              children=[
                  _node("subsection", "वन श्रोतको अवस्था विश्लेषण", "Resource Analysis", ""),
                  _node("subsection", "प्रमुख उपलब्धिहरू", "Achievements", ""),
                  _node("subsection", "आर्थिक विश्लेषण", "Economic Analysis", ""),
                  _node("subsection", "सकारात्मक पक्षहरू", "Positive Aspects", ""),
                  _node("subsection", "चुनौतीहरू", "Challenges", ""),
                  _node("subsection", "सुधार गर्नुपर्ने पक्षहरू", "Improvements", ""),
                  _node("subsection", "व्यवस्थापनको संक्षिप्त समीक्षा", "Management Review", ""),
              ]),

        # ── Section ७: सर्वेक्षण, विश्लेषण ──
        _node("section", "वनस्रोत सर्वेक्षण, विश्लेषण, वन संवर्द्धन प्रणाली तथा व्यवस्थापन", "Survey and Management System",
              "यस वनको {{blocks_count}} वटा ब्लकमा सर्वेक्षण गरिएको थियो।",
              children=[
                  _node("subsection", "भू-उपयोग", "Land Use",
                        "{{landcover_dominant}} मुख्य भू-उपयोग हो।"),
                  _node("subsection", "ब्लक/कम्पार्टमेण्ट विभाजन", "Block Division",
                        "कुल {{blocks_count}} वटा ब्लक रहेका छन्।"),
                  _node("subsection", "वन संवर्द्धन प्रणाली छनोट", "Silvicultural System", ""),
                  _node("subsection", "वन संवर्द्धन प्रणाली तथा क्रियाकलाप", "Activities", ""),
                  _node("subsection", "सङ्कलन चक्र तथा पुनरोत्पादन", "Harvest Cycle", ""),
              ]),

        # ── Section ८: उत्पादन र आपूर्ति ──
        _node("section", "वन पैदावार उत्पादन र आपूर्तिको तरिका", "Production and Supply",
              "प्रतिहेक्टर growing stock {{fi_growing_stock_m3_per_ha}} घनमिटर।"),

        # ── Section ९: संरक्षण ──
        _node("section", "संरक्षण तथा संवर्द्धन कार्य व्यवस्थापन", "Conservation",
              "{{forest_health_dominant}} वन स्वास्थ्य अवस्था रहेको छ।",
              children=[
                  _node("subsection", "डढेलो तथा चरिचरन नियन्त्रण", "Fire and Grazing Control",
                        "{{forest_loss_hectares}} हेक्टर वन क्षति भएको छ।"),
                  _node("subsection", "रोग किरा तथा मिचाहा प्रजाति नियन्त्रण", "Pest Control", ""),
                  _node("subsection", "अतिक्रमण, चोरी शिकार तथा कटानी नियन्त्रण", "Encroachment Control", ""),
                  _node("subsection", "वन्यजन्तु तथा जैविक मार्ग संरक्षण", "Wildlife Conservation",
                        "{{bio_total_species}} प्रजातिहरू पाइन्छन् (वनस्पति: {{bio_vegetation_count}}, जनावर: {{bio_animal_count}})।"),
                  _node("subsection", "वातावरणीय सेवा", "Environmental Services", ""),
                  _node("subsection", "पानीका मुहान संरक्षण", "Water Source Conservation", ""),
                  _node("subsection", "जलवायुजन्य जोखिम न्यूनीकरण", "Climate Risk", ""),
                  _node("subsection", "वन संवर्द्धन क्रियाकलाप", "Forest Enhancement Activities", ""),
                  _node("subsection", "परम्परागत ज्ञान", "Traditional Knowledge", ""),
              ]),

        # ── Section १०: आय-आर्जन ──
        _node("section", "वन पैदावारमा आधारित आय-आर्जन", "Income Generation",
              "{{activities_total}} वटा क्रियाकलाप प्रस्तावित छन्। कुल बजेट रु. {{activities_total_budget}}।",
              children=[
                  _node("subsection", "सामाजिक तथा आर्थिक विकास", "Socio-economic Development", ""),
                  _node("subsection", "सामुदायिक विकास", "Community Development", ""),
                  _node("subsection", "वैकल्पिक उर्जा", "Alternative Energy", ""),
                  _node("subsection", "संस्थागत तथा मानविय विकास", "Institutional Development", ""),
                  _node("subsection", "वनमा आधारित उद्यम", "Forest-based Enterprise", ""),
                  _node("subsection", "पर्या-पर्यटन", "Eco-tourism", ""),
              ]),

        # ── Section ११: बजेट ──
        _node("section", "वार्षिक बजेट तथा कार्यक्रम", "Annual Budget and Program",
              "{{ya_available}} कुल बजेट रु. {{ya_total_ten_year_budget}}।",
              children=[
                  _node("subsection", "वर्ष अनुसार बजेट वितरण", "Year-wise Budget Distribution",
                        "{{chart:ya_budget_year_bar}}"),
                  _node("subsection", "कार्यक्रम अनुसार बजेट", "Program-wise Budget",
                        "{{chart:ya_program_pie}}"),
                  _node("subsection", "वर्ष अनुसार बजेट सारांश", "Year-wise Budget Summary",
                        "{{ya_year_summary}}"),
                  _node("subsection", "क्रियाकलाप योजना विस्तृत विवरण", "Activity Plan Detail",
                        "{{ya_activity_plan_detail}}"),
              ]),

        # ── Section १२: वार्षिक क्रियाकलाप ──
        _node("section", "व्यवस्थापन कार्ययोजना अवधिको लागि वार्षिक क्रियाकलाप तथा बजेट", "Annual Activities",
              children=[
                  _node("subsection", "दश वर्षे कार्यक्रम", "Ten-year Program",
                        "{{plan_year_start}} देखि {{plan_year_end}} सम्मको कार्यक्रम।"),
                  _node("subsection", "दश वर्षे क्रियाकलाप विवरण (गतिविधि × वर्ष)", "10-Year Activity Matrix",
                        "{{ya_plan_matrix}}"),
                  _node("subsection", "क्रियाकलाप योजना विस्तृत विवरण", "Activity Plan Detail",
                        "{{ya_activity_plan_detail}}"),
                  _node("subsection", "कार्यक्रम अनुसार बजेट विवरण", "Program-wise Budget Details",
                        "{{ya_program_budget}}"),
              ]),

        # ── Section १३: सहकार्य ──
        _node("section", "छिमेकी समूहसँग सहकार्य तथा साझेदारी", "Collaboration",
              "{{ug_total_settlements}} वटा बस्तीहरू वनको वरिपरि रहेका छन्।",
              children=[
                  _node("subsection", "वन पैदावर उपलब्ध गराउने व्यवस्था", "Forest Product Distribution", ""),
                  _node("subsection", "लिलाम बिक्री प्रक्रियाहरू", "Auction Process", ""),
              ]),

        # ── Section १४: वित्तीय विश्लेषण ──
        _node("section", "व्यवस्थापन कार्ययोजनाको वित्तीय विश्लेषण", "Financial Analysis",
              "कुल बजेट रु. {{activities_total_budget}} रहेको छ।",
              children=[
                  _node("subsection", "वित्तिय विश्लेषणको अवस्था", "Financial Status",
                        "कुल खर्च रु. {{activities_total_budget}} अनुमानित छ।"),
              ]),

        # ── Section १५: अनुगमन ──
        _node("section", "पुनरावलोकन, अनुगमन, मूल्याङ्कन", "Monitoring and Evaluation",
              children=[
                  _node("subsection", "स्वःअनूगमन तथा मूल्यांकन", "Self-monitoring", ""),
                  _node("subsection", "सार्वजनिक सुनुवाई", "Public Hearing", ""),
                  _node("subsection", "लेखापरिक्षण", "Audit", ""),
                  _node("subsection", "अनुगमन र लेखापरिक्षण", "Monitoring and Audit", ""),
                  _node("subsection", "समीक्षा", "Review", ""),
                  _node("subsection", "अनुगमनमा सहयोग", "Monitoring Support", ""),
                  _node("subsection", "भत्ता सम्बन्धी व्यवस्था", "Allowance", ""),
              ]),

        # ── Section १६: निषेधित ──
        _node("section", "सामुदायिक वनमा निषेधित कार्यहरू", "Prohibited Activities",
              "निम्न कार्यहरू निषेधित गरिएका छन्:"),

        # ── Section १७: वन अपराध ──
        _node("section", "वन अपराध र दण्ड जरिवाना", "Forest Crime and Penalties",
              children=[
                  _node("subsection", "अपराध र दण्ड जरिवाना", "Crime and Penalty", ""),
                  _node("subsection", "दण्ड जरिवाना", "Penalties", ""),
              ]),

        # ── Section १८: विविध ──
        _node("section", "विविध", "Miscellaneous",
              children=[
                  _node("subsection", "विविध जानकारी", "Miscellaneous Information", ""),
                  _node("subsection", "सोच तालिका (Logical Framework)", "Logical Framework", ""),
              ]),
    ]


def get_appendix_seed_nodes() -> List[TreeNode]:
    return [
        _node("appendix", "अनुसूची १: घरधुरी विवरण", "Appendix 1: Household Details", is_locked=True),
        _node("appendix", "अनुसूची २: व्यवस्थापन कार्ययोजना तर्जुमा समिति", "Appendix 2: Management Committee", is_locked=True),
        _node("appendix", "अनुसूची ३: बस्ती विवरण", "Appendix 3: Settlement Details", is_locked=True),
        _node("appendix", "अनुसूची ४: नक्सा", "Appendix 4: Maps", is_locked=True),
        _node("appendix", "अनुसूची ५: वन पैदावार विवरण", "Appendix 5: Forest Products", is_locked=True),
        _node("appendix", "अनुसूची ६: बैठक मिनेट", "Appendix 6: Meeting Minutes", is_locked=True),
        _node("appendix", "अनुसूची ७: लेखापरीक्षण प्रतिवेदन", "Appendix 7: Audit Report", is_locked=True),
        _node("appendix", "अनुसूची ८: उपभोक्ता समिति निर्वाचन", "Appendix 8: Committee Election", is_locked=True),
        _node("appendix", "अनुसूची ९: सार्वजनिक सुनुवाई", "Appendix 9: Public Hearing", is_locked=True),
        _node("appendix", "अनुसूची १०: तालिका १-३२", "Appendix 10: Tables 1-32", is_locked=True,
              content_type="table", table_id="tables_1_32"),
    ]


def get_full_seed_document() -> List[TreeNode]:
    tree = get_default_seed_tree()
    tree.extend(get_appendix_seed_nodes())
    return tree
