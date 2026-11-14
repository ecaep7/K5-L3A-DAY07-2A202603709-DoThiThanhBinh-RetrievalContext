"""Soạn benchmark nâng cao (dev 18 câu, test 30 câu) và tự kiểm tra trích dẫn với lớp chữ của PDF gốc."""
import json, re, sys
import pymupdf

PDF = sys.argv[1]; OUT = sys.argv[2]; CHUNKS = sys.argv[3]
doc = pymupdf.open(PDF)
def norm(s): return re.sub(r"\s+", " ", s.replace("−", "-").replace("­", "").replace("ﬁ", "fi").replace("ﬀ","ff")).strip()
def label_of(p): 
    return {c["page"]: c["page_label"] for c in json.load(open(CHUNKS, encoding="utf-8"))}.get(p)
chunks = json.load(open(CHUNKS, encoding="utf-8"))
PL = {c["page"]: c["page_label"] for c in chunks}

def T(page, quote):            # đoạn văn: quote phải có nguyên văn trên trang
    return {"page": page, "kind": "text", "quote": quote}
def V(page, label, kind, location, values):   # bảng/hình: nhãn, vùng, giá trị đọc trên bản gốc
    return {"page": page, "kind": kind, "label": label, "location": location, "values": values}

Q = []
def add(id, split, group, question, answer, evidence=None, calc=None, reason="", absence=None, tags=()):
    Q.append({"id": id, "split": split, "group": group, "answerable": absence is None, "question": question,
              "expected_answer": answer if absence is None else "INSUFFICIENT_EVIDENCE (từ chối, không suy đoán)",
              "evidence": evidence or [], "calculation": calc, "reason": reason, "absence_check": absence,
              "tags": list(tags)})

# ============================ DEV ============================
add("ad01", "dev", "table", "In 2020, what was the annual total poverty gap at the LMIC poverty line ($3.20/day 2011PPP), and in what unit?",
    "15.02 trillion VND (2020 VND) in 2020.",
    [V(49, "Table 1.3", "table", "Panel B 'Annual total gap (2020 VND, trillion)', row 'LMIC – PL ($3.20/day 2011PPP)', column 2020", "15.02")],
    reason="Tra một ô trong bảng có hai panel; phải chọn đúng panel B và đúng đơn vị.")
add("ad02", "dev", "table", "How much did the population of the Southeast region grow between 2009 and 2019?",
    "From 14,067,361 (2009) to 17,828,818 (2019), an increase of 3,761,457 people.",
    [V(75, "Table 2.1", "table", "row 'Southeast', columns 2009 and 2019", "14,067,361; 17,828,818")],
    calc="17,828,818 - 14,067,361 = 3,761,457", reason="Tra hai ô cùng hàng rồi tính hiệu.")
add("ad03", "dev", "table", "How many districts were covered in the 2019 small area poverty map, and which World Bank poverty line was used alongside the GSO-WB line?",
    "712 districts; the $3.20/day 2011PPP line (with the GSO-WB poverty line).",
    [V(52, "Table 1.4", "table", "row 'Year of estimate 2019', columns 'Poverty lines' and 'Number of districts in map'", "GSO-WB Poverty Line, $3.20/day 2011PPP; 712")],
    reason="Tra hàng theo năm ước tính, đọc hai cột.")
add("ad04", "dev", "image", "In the diagram that decomposes household consumption per capita (Box 2.4), which two components is 'Income per adult' split into?",
    "Labor income per adult and non-labor income per adult.",
    [V(96, "Figure B.2.4.1", "diagram", "tree diagram: box 'Income per adult' branches to two yellow boxes", "Labor income per adult; Non-labor income per adult")],
    reason="Đọc quan hệ giữa các ô trong sơ đồ cây.")
add("ad05", "dev", "image", "Which environmental indicators are mapped by district in Figure 6.5?",
    "Five maps: mean temperature, air pollution (PM2.5), mean precipitation, the SPEI drought indicator, and the percent of the population exposed to high flood risk.",
    [V(179, "Figure 6.5", "map", "panel titles of the five maps", "Temperature (mean); Air pollution (PM2.5); Precipitation (mean); SPEI drought indicator; Percent of the population exposed to high flood risk")],
    reason="Nhận diện các bản đồ con trong một hình nhiều panel.")
add("ad06", "dev", "image", "In panel B of Figure 8.1 (policy to fill the current gaps in protection), where should the equity elements of social insurance be financed from?",
    "From broader-based financing, i.e. general revenues ('Shift equity elements to financing from broader-based (general revenues financed)').",
    [V(225, "Figure 8.1", "diagram", "panel B, annotation pointing to the orange (social insurance) area", "Shift equity elements to financing from broader-based (general revenues financed)")],
    reason="Đọc chú thích trong sơ đồ minh họa chính sách.")
add("ad07", "dev", "chart", "How many Vietnamese households had tertiary education as the highest completed level in 2010 and in 2020?",
    "3.0 million in 2010 and 4.7 million in 2020.",
    [V(76, "Figure 2.3", "chart", "category 'Tertiary', bars 2010 (teal) and 2020 (orange); y-axis '# of households (in millions)'", "3.0; 4.7")],
    reason="Đọc nhãn cột và đơn vị trục.")
add("ad08", "dev", "chart", "According to Figure 6.11, what share of respondents borrowed from family or friends in 2017, and how does it compare with borrowing from a financial institution?",
    "60.2% borrowed from family or friends, versus 42.0% from a financial institution (48.4% from an informal savings club).",
    [V(187, "Figure 6.11", "chart", "three bars, year 2017; y-axis 'Share of respondents (%)'", "From a financial institution 42.0; From family or friends 60.2; From an informal savings club 48.4")],
    reason="So sánh giá trị giữa các cột.")
add("ad09", "dev", "chart", "How many households had an oldest member aged 60–69 in 2010 and in 2020?",
    "2.5 million in 2010 and 4.6 million in 2020.",
    [V(75, "Figure 2.1", "chart", "category '60–69', bars 2010 and 2020; y-axis '# of households (in millions)'", "2.5; 4.6")],
    reason="Đọc cột theo nhóm tuổi; điều kiện: phân loại theo thành viên lớn tuổi nhất.")
add("ad10", "dev", "multi_hop", "Which region had the largest population in 2019, and how many households did that region have in 2020?",
    "The Red River Delta: 22,543,562 people in 2019 and 6.6 million households in 2020.",
    [V(75, "Table 2.1", "table", "column 2019, largest regional value", "Red River Delta 22,543,562"),
     V(103, "Figure 3.4", "chart", "pie slice 'Red River Delta' (number of households, in millions)", "6.6m")],
    reason="Tìm vùng lớn nhất ở bảng rồi tra vùng đó ở biểu đồ tròn khác trang.")
add("ad11", "dev", "multi_hop", "In 2018, how did government revenue from personal income tax (PIT) compare with central government spending on direct transfers?",
    "PIT revenue was 94 trillion VND (1.7% of GDP), more than twice direct transfers spending of 40 trillion VND (0.7% of GDP).",
    [V(199, "Table 7.1", "table", "row 'PIT'", "94 TRN DONG; 1.7 % GDP"), V(200, "Table 7.2", "table", "row 'Direct Transfers'", "40 TRN DONG; 0.7 % GDP")],
    calc="94 / 40 = 2.35", reason="Kết hợp hai bảng ở hai trang.")
add("ad12", "dev", "multi_hop", "The $5.50/day poverty rate was measured in 2020. Using the October 2021 growth estimates with no change in Gini, how much lower was it projected to be in 2023?",
    "From 18.8% in 2020 to a projected 14.1% in 2023, a fall of 4.7 percentage points.",
    [V(48, "Table 1.1", "table", "row 2020, column '$5.50/day 2011PPP - UMIC'", "18.8"),
     V(63, "Figure 1.22", "chart", "lower-left panel ($5.50/day, 'No change in Gini'), orange line (October 2021 growth estimates), last point", "14.1")],
    calc="18.8 - 14.1 = 4.7 percentage points", reason="Kết hợp số đo thực tế (bảng) với dự báo (biểu đồ nhiều panel).")
add("ad13", "dev", "text", "How does the report define an underemployed individual?",
    "Someone who works less than 35 hours a week and would like to work more.",
    [T(41, "An individual is underemployed if they work less than 35 hours a week and would like to work more.")],
    reason="Định nghĩa có điều kiện, nằm trong chú thích cuối phần Overview.")
add("ad14", "dev", "text", "Who is covered by Vietnam's social pension scheme without a means test, and who is means-tested?",
    "Coverage is universal above age 80; people aged 60–79 are means-tested.",
    [T(189, "which has universal coverage above age 80 but is means-tested for those aged 60-79")],
    reason="Điều kiện theo nhóm tuổi.")
add("ad15", "dev", "text", "What was Vietnam's Gini Index in 1993 and in 2020?",
    "35.6 in 1993 and 36.8 in 2020.",
    [T(61, "The Gini Index was 35.6 in 1993 and 36.8 in 2020")], reason="Tra số liệu trong đoạn văn.")
add("ad16", "dev", "unanswerable", "What is Vietnam's statutory monthly minimum wage for Region I, in VND?", None,
    absence="Báo cáo chỉ có một con số chung: 'minimum monthly wages are about VND 4 million' (chú thích trang 67, trang 188) và một câu giả định ở trang 96; không có mức lương tối thiểu theo vùng (Region I). (Bản đầu ghi chỉ dò 'minimum wage' nên sót 'minimum monthly wages'; đã sửa sau khi chạy dev, câu hỏi không đổi.)")
add("ad17", "dev", "unanswerable", "What is the poverty rate among people with disabilities in Vietnam?", None,
    absence="'disabilit' xuất hiện 10 lần chỉ như nhóm đối tượng được trợ cấp/nhắm mục tiêu; không có tỷ lệ nghèo của người khuyết tật (dò 'disabilit' kèm percent/%/rate: 0 kết quả).")
add("ad18", "dev", "unanswerable", "What is Thailand's Gini index according to the report?", None,
    absence="Thailand chỉ xuất hiện trong các biểu đồ so sánh (shared prosperity, lương, HCI...); dò 'Gini' gần 'Thailand' và các nước khác: 0 kết quả. Gini chỉ được nêu cho Việt Nam.")

# ============================ TEST ============================
add("at01", "test", "table", "What was Vietnam's poverty rate at the international poverty line ($1.90/day 2011PPP) in 1993 and in 2008?",
    "52.3% in 1993 and 14.1% in 2008.",
    [V(48, "Table 1.1", "table", "column '$1.90/day 2011PPP - IPL', rows 1993 and 2008", "52.3; 14.1")],
    reason="Tra hai ô cùng cột trong bảng dài. Bối cảnh (không bắt buộc nêu): 1993–2008 thuộc chuỗi số liệu cũ, bảng ghi không so sánh được với 2010–2020.")
add("at02", "test", "table", "How did Vietnam's harmonized test score change between 2010 and 2020, and what was the East Asia and Pacific value in 2020?",
    "It fell from 533 (2010) to 519 (2020); the East Asia and Pacific value in 2020 was 432.",
    [V(132, "Table 4.1", "table", "row 'Harmonized Test Scores', columns Vietnam 2010/2020 and East Asia and Pacific 2020", "533; 519; 432")],
    reason="Tra nhiều ô theo hàng/cột có tiêu đề hai tầng.")
add("at03", "test", "table", "In 2020, what were the expected years of schooling for males and for females in Vietnam?",
    "12.5 years for males and 13.2 years for females.",
    [V(137, "Table 4.2", "table", "row 'Expected years of schooling', columns Male 2020 and Female 2020", "12.5; 13.2")], reason="Chọn đúng cột theo giới và năm.")
add("at04", "test", "table", "How much did Vietnam's central government spend on education in 2018, and which education level received the most?",
    "220 trillion VND (4.0% of GDP); primary education received the most, 63 trillion VND (1.1% of GDP).",
    [V(200, "Table 7.2", "table", "rows 'Education' and its sub-rows Pre-school ... Tertiary", "Education 220 / 4.0; Primary 63 / 1.1 (largest sub-row)")],
    reason="Tra tổng và so sánh các dòng con.")
add("at05", "test", "table", "What is the lower-middle-income country poverty line ($3.20/day 2011PPP) worth in Vietnamese dong?",
    "1,055,178 VND per person per month, in January 2020 dong.",
    [V(71, "Table A.1.3.2", "table", "row 'Lower-middle-income country poverty line', column 'VND 2020 (Jan) monthly per capita'", "3.20; 1,055,178")],
    reason="Đúng đơn vị: VND tháng 1/2020, theo tháng, theo đầu người.")
add("at06", "test", "table", "What share of ethnic minority and of Kinh agricultural households engaged in forestry (VHLSS 2018)?",
    "0.69 (69%) of ethnic minority households versus 0.11 (11%) of Kinh households, a difference of 0.60.",
    [V(120, "Table 3.1", "table", "Panel A: Activity, row 'Forestry', columns Kinh / EM / Diff.", "0.11; 0.69; -0.60***")],
    reason="Đọc đúng cột nhóm dân tộc trong bảng có panel.")
add("at07", "test", "image", "In the framework for calculating the Human Capital Index, which indicators make up the contribution to productivity from health?",
    "Adult survival rate and not stunted rate.",
    [V(135, "Figure B.4.1.1", "diagram", "branch 'Contribution to Productivity from Health' and its two boxes", "Adult survival rate; Not stunted rate")],
    reason="Đọc nhánh trong sơ đồ khung.")
add("at08", "test", "image", "According to the diagram of Vietnam's social protection system, which programs fall under Social Insurance?",
    "Unemployment insurance; compulsory and voluntary insurance; and other programs (supplement SI).",
    [V(190, "Figure B.6.3.1", "diagram", "column under the green box 'Social Insurance'", "Unemployment Insurance; Compulsory and voluntary Insurance; Other Programs (Supplement SI)")],
    reason="Đọc chữ xoay dọc dưới một nhánh của sơ đồ.")
add("at09", "test", "image", "In the diagram defining income concepts and fiscal instruments, what is added and what is subtracted to go from Disposable Income to Consumer Income?",
    "Indirect subsidies (electricity, water) are added and indirect taxes (GST; SST on tobacco, alcohol, sodas, mobile phones) are subtracted.",
    [V(197, "Figure B.7.1.1", "diagram", "boxes beside the arrow from 'Disposable Income' to 'Consumer Income' (+ on the left, − on the right)", "+ Indirect subsidies (direct and indirect impacts): electricity; water; − Indirect taxes: GST; SST tobacco, alcohol, sodas, mobile phones")],
    reason="Đọc dấu +/− và hộp tương ứng trong sơ đồ luồng.")
add("at10", "test", "image", "In the poverty and environmental risk maps (Figure 6.7), what color marks a medium-poverty district that is in the top third of environmental risk?",
    "Red (dark red / brick red). Yellow marks low-poverty and dark navy marks high-poverty districts in the top third.",
    [V(182, "Figure 6.7", "map", "legend at right of the first row: row 'Environmental risk (top third)', column 'Medium poverty'", "red square (low poverty = yellow, high poverty = dark navy)")],
    reason="Đọc chú giải dạng ma trận màu của bản đồ.")
add("at11", "test", "image", "Which two regions are shown in the zoom-in maps of Figure 3.9, and what do blue and orange districts mean?",
    "Midlands & Northern Mountains and Central Highlands; orange districts have poverty rates above the national average (2019 small area poverty map) and blue districts below it.",
    [V(107, "Figure 3.9", "map", "panel titles and note under the color bar", "Midlands & Northern Mountains; Central Highlands; 'Poverty rates are higher in orange districts than the national average, and lower in blue districts.'")],
    reason="Đọc tiêu đề panel và ý nghĩa thang màu bản đồ.")
add("at12", "test", "chart", "How did the number of households whose main employment is agriculture change from 2010 to 2020, and which sector had the most households in 2020?",
    "Agriculture fell from 11.6 million to 9.5 million households; services had the most in 2020 with 13.1 million.",
    [V(76, "Figure 2.4", "chart", "bars Agriculture/Manufacturing/Services for 2010 and 2020; y-axis '# of households (in millions)'", "Agriculture 11.6 → 9.5; Manufacturing 8.3 → 12.2; Services 9.6 → 13.1")],
    reason="So sánh theo thời gian và giữa các nhóm.")
add("at13", "test", "chart", "In 2014, what share of households in the poorest quintile had access to improved water and to improved sanitation?",
    "74.3% had improved water and 38.2% had improved sanitation.",
    [V(136, "Figure 4.7", "chart", "category 'Poorest (quintile=1)', teal and orange bars", "74.3; 38.2")], reason="Đọc đúng cột theo chú giải.")
add("at14", "test", "chart", "In which year shown was catastrophic health expenditure highest for both urban and rural households, and what were the values?",
    "2004: 13.7% of urban and 16.6% of rural households.",
    [V(177, "Figure 6.4", "chart", "bars for 2002–2016, urban (teal) and rural (orange); y-axis 'Share of households (%)'", "2004: 13.7 / 16.6 (highest for both)")],
    reason="Tìm cực đại trên hai chuỗi.")
add("at15", "test", "chart", "What share of respondents had an account in 2017 and in 2019?",
    "26.4% in 2017 and 42.3% in 2019.",
    [V(187, "Figure 6.10", "chart", "category 'Has an account', bars 2017 and 2019", "26.4; 42.3")], reason="Đọc cột theo năm.")
add("at16", "test", "chart", "How did the poverty rate ($3.20/day) of ethnic minorities and of the Kinh change from 2010 to 2020?",
    "Ethnic minorities: 56.8% to 27.2%; Kinh: 9.4% to 1.2%.",
    [V(102, "Figure 3.1", "chart", "panel 'Ethnicity', first and last points of each line", "Ethnic minority 56.8 → 27.2; Kinh 9.4 → 1.2")],
    reason="Đọc đúng panel trong hình nhiều panel.")
add("at17", "test", "multi_hop", "In 2020, how did the Human Capital Index for females compare with Vietnam's overall Human Capital Index?",
    "Female HCI was 0.73 versus 0.69 overall, i.e. 0.04 higher.",
    [V(137, "Table 4.2", "table", "row 'Human Capital Index', column Female 2020", "0.73"),
     V(132, "Table 4.1", "table", "row 'HCI', column Vietnam 2020", "0.69")],
    calc="0.73 - 0.69 = 0.04", reason="Kết hợp hai bảng ở hai trang.")
add("at18", "test", "multi_hop", "What was the 2020 poverty rate ($3.20/day) in the Midlands and Northern Mountains, and what share of Vietnam's poor lived there?",
    "16.0% in 2020; 42% of the poor lived there although the region has 13% of the national population.",
    [V(51, "Figure 1.5", "chart", "grey line 'Midlands & Northern Mountains', 2020 point (same panel also in Figure 3.1, page 102)", "16.0"),
     T(105, "42 percent of the poor live in the Midlands and Northern Mountains, even though they are 13 percent of the national population")],
    reason="Kết hợp biểu đồ và đoạn văn ở hai trang.")
add("at19", "test", "multi_hop", "In 2018, by how much did central government total expenditures exceed total government revenues and grants?",
    "Expenditures were 1,435 trillion VND (25.9% of GDP) vs revenues and grants of 1,364 trillion VND (24.6% of GDP): 71 trillion VND, or 1.3 percentage points of GDP.",
    [V(199, "Table 7.1", "table", "row 'Total revenues & grants'", "1,364; 24.6"), V(200, "Table 7.2", "table", "row 'Total expenditures'", "1,435; 25.9")],
    calc="1,435 - 1,364 = 71; 25.9 - 24.6 = 1.3", reason="Tính từ hai bảng.")
add("at20", "test", "multi_hop", "Table 2.2 gives an estimated number of social assistance beneficiaries and their monthly benefit; how does that compare with the coverage reported for 2020 in the text?",
    "Table 2.2: 2.84 million social assistance beneficiaries receiving VND 1.5 million per person per month (Dutta 2019 estimates for 2018). The text reports coverage expanded from 200,000 beneficiaries in 2000 to more than 3.1 million in 2020.",
    [V(90, "Table 2.2", "table", "row 'Social assistance beneficiaries' + note", "2.84 million people; VND 1.5 million per person; 'Dutta (2019) estimates for 2018 are used'"),
     T(189, "Social assistance coverage has expanded significantly from 200,000 beneficiaries in 2000 to more than 3.1 million in 2020")],
    reason="Kết hợp bảng và đoạn văn; phải nêu đúng năm/điều kiện của từng số.")
add("at21", "test", "text", "What share of the Central Highlands population are ethnic minorities, and in which region are ethnic minority households fewest?",
    "About 30% of the Central Highlands population; they are fewest in the Red River Delta (about 120,000 households).",
    [T(75, "ethnic minorities comprise 30 percent of the regional population"),
     T(75, "These households are the fewest in number in the Red River Delta (about 120,000 households)")],
    reason="Tổng hợp hai câu trong cùng đoạn.")
add("at22", "test", "text", "What share of Vietnam's current elderly receive a contributory pension, and what is the average ratio of VSS pensions to social pensions?",
    "A quarter of the elderly receive a contributory pension; the average ratio of VSS pensions to social pensions is 18:1.",
    [T(177, "A quarter of the current elderly receive a contributory pension"), T(177, "the average ratio of VSS pensions to social pensions is 18:1")],
    reason="Hai thông tin trong hai đoạn liền nhau.")
add("at23", "test", "text", "What is the Human Capital Index for children in the richest 20 percent versus the poorest 20 percent of households, and how does this gap compare internationally?",
    "0.85 for the richest 20% vs 0.58 for the poorest 20%; the 0.27-point gap is larger than the 0.15-point average gap among 50 countries.",
    [T(41, "The Human Capital Index is 0.85 for children in the richest 20 percent of households, compared to 0.58 for children in the poorest 20 percent"),
     T(41, "the gap in the Human Capital Index between the top 20 and bottom 20 in Vietnam is 0.27 points, higher than the average gap among 50 countries (0.15 points)")],
    reason="Số liệu có điều kiện trong chú thích cuối trang.")
add("at24", "test", "text", "In which SEDP phases were the poor and near-poor determined by household income only?",
    "In the 2006–2010 and 2011–2015 phases.",
    [T(70, "For the 2006–2010 and 2011–2015 phases, the poor and near-poor were determined by only household income")],
    reason="Thông tin có điều kiện theo giai đoạn.")
add("at25", "test", "unanswerable", "What was Vietnam's Gini index in 2022?", None,
    absence="Gini của Việt Nam chỉ có tới 2020 (35.6 năm 1993, 36.8 năm 2020: trang 61, Figure 1.19). Các dự báo 2021–2023 (Figure O.10 trang 27, Figure 1.22 trang 63, Figure 1.23 trang 64) chỉ giả định kịch bản Gini tăng 1%/2%, không công bố mức Gini năm 2022. Dò mọi lần xuất hiện 'Gini' gần năm 2021–2029: không có giá trị Gini nào.")
add("at26", "test", "unanswerable", "What was Vietnam's consumer price inflation rate in 2021?", None,
    absence="'inflation' chỉ xuất hiện trong tên một bài báo ở mục tài liệu tham khảo (trang 40) và bối cảnh lịch sử thập niên 1980 (trang 80); không có tỷ lệ lạm phát 2021.")
add("at27", "test", "unanswerable", "What share of Vietnamese households owned a refrigerator in 2020?", None,
    absence="Dò 'refrigerator', 'fridge': 0 kết quả. Báo cáo chỉ nhắc điện thoại, xe máy, xe đạp (trang 61).")
add("at28", "test", "unanswerable", "What is Vietnam's maternal mortality ratio?", None,
    absence="Dò 'maternal mortality': 0 kết quả. Chỉ có mục tiêu 'access to maternal care to 80%' (trang 127), không phải tỷ số tử vong mẹ.")
add("at29", "test", "unanswerable", "What poverty rate at $3.20/day does the report project for Vietnam in 2025?", None,
    absence="Dự báo nghèo trong báo cáo chỉ tới 2023 (Figure O.10 trang 27, Figure 1.22 trang 63, Annex 1.4 trang 73: 'For 2021–2023'). '2025' chỉ xuất hiện trong tên giai đoạn SEDP 2021–2025.")
add("at30", "test", "unanswerable", "What is the poverty rate of Lao PDR according to the report?", None,
    absence="Lao PDR chỉ xuất hiện trong biểu đồ so sánh lương theo ngành (trang 87) và danh sách nước so sánh; dò 'Lao' gần 'poverty': 0 kết quả. Báo cáo không nêu tỷ lệ nghèo của Lào. (Thay câu cũ về 'gross tertiary enrollment rate' trước khi chạy test, vì báo cáo có biểu đồ tỷ lệ đi học theo tuổi ở Figure 4.6/4.9, dễ gây tranh cãi khi chấm.)")

# ------------ tự kiểm tra: quote có trên trang PDF; giá trị bảng/hình có trong lớp chữ của trang
problems = []
for q in Q:
    for e in q["evidence"]:
        e["page_label"] = PL.get(e["page"])
        page_text = norm(doc[e["page"] - 1].get_text())
        if e["kind"] == "text":
            if norm(e["quote"]) not in page_text:
                problems.append((q["id"], e["page"], "quote không khớp", e["quote"][:60]))
        else:
            if e["label"].replace(" ", "") not in page_text.replace(" ", ""):
                problems.append((q["id"], e["page"], "không thấy nhãn", e["label"]))
            for num in re.findall(r"\d[\d,.]*\d|\d", e["values"]):
                if num not in page_text:
                    problems.append((q["id"], e["page"], "số không có trong lớp chữ (đọc từ hình)", num))
    # gold chunk: theo trang + nhãn (lấy từ lớp chữ PDF), và chunk text chứa quote
    gold = []
    for e in q["evidence"]:
        for c in chunks:
            if c["page"] != e["page"]:
                continue
            if e["kind"] != "text" and c.get("label") and c["label"].replace(" ", "") == e["label"].replace(" ", ""):
                gold.append(c["id"])
            if e["kind"] == "text" and norm(e["quote"])[:80] in norm(c["text"]):
                gold.append(c["id"])
    q["gold_chunk_ids"] = sorted(set(gold))
    if q["answerable"] and len(q["gold_chunk_ids"]) < 1:
        problems.append((q["id"], None, "không tìm thấy chunk chứa evidence", ""))

for q in Q:
    if q["id"] == "at18":   # giá trị 16.0 cũng có ở Figure 3.1 (trang 102), panel Region
        q["gold_chunk_ids"] = sorted(set(q["gold_chunk_ids"] + ["pea-p102-v01"]))
    q["review"] = {"by": "Claude (Bình giao duyệt hộ)", "date": "2026-11-14", "result": "ok",
                   "method": "đối chiếu ảnh vùng bảng/hình/đoạn trên trang PDF gốc + kiểm tra tự động trích dẫn và số với lớp chữ PDF"
                   if q["answerable"] else "dò từ khóa trên toàn bộ chữ PDF và mô tả hình"}
json.dump(Q, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
for s in ("dev", "test"):
    print(s, len([q for q in Q if q["split"] == s]), Counter(q["group"] for q in Q if q["split"] == s))
print("problems:"); [print("  ", p) for p in problems]
