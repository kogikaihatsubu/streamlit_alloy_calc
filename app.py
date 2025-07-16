import streamlit as st
st.set_page_config(layout="wide")

import pandas as pd
import numpy as np
from scipy.optimize import linprog, lsq_linear
import json
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import io

# CSV読み込み（エンコード: ANTI対応）
def read_csv_anti(filename, **kwargs):
    encodings = ['cp932', 'utf-8', 'utf-8-sig', 'shift_jis']
    for encoding in encodings:
        try:
            return pd.read_csv(filename, encoding=encoding, **kwargs)
        except Exception:
            continue
    # 全て失敗した場合
    st.error(f"CSVファイル '{filename}' の読み込みに失敗しました。")
    return pd.DataFrame()

materials_df = read_csv_anti("materials.csv", index_col=0)
additives_df = read_csv_anti("additives.csv", index_col=0)

elements = ['C','Si','Mn','P','S','Ni','Cr','Mo','Ti','V','Cu','W','Sn','Al','Mg','Zn']  # Feは除外



st.title("合金配合計算システム")

# 保存・読み込み機能
save_dir = "saved_configs"
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# 保存・読み込み機能
with st.container(border=True):
    st.header("💾 設定ファイルの操作")
    
    # 保存済み設定の選択とボタンを横並びに配置
    saved_files = [f for f in os.listdir(save_dir) if f.endswith('.json')] if os.path.exists(save_dir) else []
    
    title_col, select_col, col1, col2, col3 = st.columns([1, 3, 0.5, 0.5, 0.5])
    
    with title_col:
        st.markdown("**保存済み設定の選択**")
    
    with select_col:
        if saved_files:
            selected_file = st.selectbox("選択してください", ["選択してください"] + saved_files, label_visibility="collapsed")
        else:
            selected_file = st.selectbox("選択してください", ["選択してください"], label_visibility="collapsed")
    
    with col1:
        if st.button("SAVE"):
            # 全タブの設定を収集
            current_test_name = st.session_state.get("test_name_input", "試験_001")
            config_data = {
                "test_name": current_test_name,
                "analysis_location": st.session_state.get("analysis_location", "東分析"),
                "selected_group": st.session_state.get("selected_group", ""),
                "timestamp": datetime.now().isoformat(),
                "tabs": {}
            }
            
            # 各タブの設定を保存
            for tab_idx in range(5):
                tab_config = {}
                # 基本設定
                tab_config["mode"] = st.session_state.get(f"mode_radio_{tab_idx}", "FCD")
                tab_config["tapping_temp"] = st.session_state.get(f"tapping_temp_{tab_idx}", 1450)
                tab_config["total_weight"] = st.session_state.get(f"total_weight_{tab_idx}", 110.0)
                tab_config["remaining_weight"] = st.session_state.get(f"remaining_weight_{tab_idx}", 0.0)
                
                # 選択された元素
                tab_config["selected_elements"] = st.session_state.get(f"selected_elements_{tab_idx}", [])
                
                # 成分目標値、許容値、判定方法
                tab_config["targets"] = {}
                tab_config["tolerances"] = {}
                tab_config["tolerance_types"] = {}
                for e in elements:
                    tab_config["targets"][e] = st.session_state.get(f"target_{e}_{tab_idx}", 0.0)
                    tab_config["tolerances"][e] = st.session_state.get(f"tol_{e}_{tab_idx}", 0.01)
                    tab_config["tolerance_types"][e] = st.session_state.get(f"tol_type_{e}_{tab_idx}", "±")
                
                # 選択された添加材
                tab_config["selected_additives"] = st.session_state.get(f"selected_additives_{tab_idx}", [])
                
                # 添加材の割合
                tab_config["additive_percents"] = {}
                selected_additives = tab_config["selected_additives"]
                for i, additive in enumerate(selected_additives):
                    key = f"additive_percent_{additive}_{tab_idx}_{i}"
                    if key in st.session_state:
                        tab_config["additive_percents"][additive] = st.session_state[key]
                    else:
                        tab_config["additive_percents"][additive] = 0.0
                
                # 選択された材料
                tab_config["selected_materials"] = st.session_state.get(f"selected_materials_widget_{tab_idx}", [])
                
                # 手動材料の量
                tab_config["manual_materials"] = {}
                for mat in ["鋼屑", "神鋼ＳＰ銑", "故銑"]:
                    tab_config["manual_materials"][mat] = st.session_state.get(f"manual_{mat}_{tab_idx}", 0.0)
                
                config_data["tabs"][f"tab_{tab_idx}"] = tab_config
            
            filename = f"{save_dir}/{current_test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            # メッセージを列分割の外に表示するためにフラグを設定
            st.session_state['save_success'] = filename
            st.rerun()
    
    with col2:
        if st.button("LOAD", disabled=(not saved_files or selected_file == "選択してください")):
            if selected_file != "選択してください":
                with open(f"{save_dir}/{selected_file}", 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 基本設定を復元
                st.session_state["analysis_location"] = config_data.get("analysis_location", "東分析")
                st.session_state["selected_group"] = config_data.get("selected_group", "")
                
                # 各タブの設定を復元
                if "tabs" in config_data:
                    for tab_idx in range(5):
                        tab_key = f"tab_{tab_idx}"
                        if tab_key in config_data["tabs"]:
                            tab_config = config_data["tabs"][tab_key]
                            
                            # 基本設定
                            st.session_state[f"mode_radio_{tab_idx}"] = tab_config.get("mode", "FCD")
                            st.session_state[f"tapping_temp_{tab_idx}"] = tab_config.get("tapping_temp", 1450)
                            st.session_state[f"total_weight_{tab_idx}"] = tab_config.get("total_weight", 110.0)
                            st.session_state[f"remaining_weight_{tab_idx}"] = tab_config.get("remaining_weight", 0.0)
                            
                            # 選択された元素
                            st.session_state[f"selected_elements_{tab_idx}"] = tab_config.get("selected_elements", [])
                            
                            # 成分目標値、許容値、判定方法
                            for e in elements:
                                if "targets" in tab_config:
                                    st.session_state[f"target_{e}_{tab_idx}"] = tab_config["targets"].get(e, 0.0)
                                if "tolerances" in tab_config:
                                    st.session_state[f"tol_{e}_{tab_idx}"] = tab_config["tolerances"].get(e, 0.01)
                                if "tolerance_types" in tab_config:
                                    st.session_state[f"tol_type_{e}_{tab_idx}"] = tab_config["tolerance_types"].get(e, "±")
                            
                            # 選択された添加材
                            st.session_state[f"selected_additives_{tab_idx}"] = tab_config.get("selected_additives", [])
                            
                            # 添加材の割合
                            if "additive_percents" in tab_config and "selected_additives" in tab_config:
                                for i, additive in enumerate(tab_config["selected_additives"]):
                                    key = f"additive_percent_{additive}_{tab_idx}_{i}"
                                    st.session_state[key] = tab_config["additive_percents"].get(additive, 0.0)
                            
                            # 選択された材料
                            st.session_state[f"selected_materials_widget_{tab_idx}"] = tab_config.get("selected_materials", [])
                            
                            # 手動材料の量
                            if "manual_materials" in tab_config:
                                for mat in ["鋼屑", "神鋼ＳＰ銑", "故銑"]:
                                    st.session_state[f"manual_{mat}_{tab_idx}"] = tab_config["manual_materials"].get(mat, 0.0)
                
                st.session_state['load_success'] = True
                st.rerun()
    
    with col3:
        if st.button("DELETE", disabled=(not saved_files or selected_file == "選択してください")):
            if selected_file != "選択してください":
                # 確認ダイアログを表示
                if 'delete_confirm' not in st.session_state:
                    st.session_state['delete_confirm'] = True
                    st.rerun()

    # 削除確認ダイアログ
    if st.session_state.get('delete_confirm', False):
        st.warning(f"⚠️ 本当に '{selected_file}' を削除しますか？")
        col_yes, col_no, _ = st.columns([1, 1, 8])
        with col_yes:
            if st.button("✅ はい", key="delete_yes"):
                os.remove(f"{save_dir}/{selected_file}")
                st.session_state['delete_success'] = True
                del st.session_state['delete_confirm']
                st.rerun()
        with col_no:
            if st.button("❌ いいえ", key="delete_no"):
                del st.session_state['delete_confirm']
                st.rerun()

    # メッセージを列分割の外で表示
    if 'save_success' in st.session_state:
        st.success(f"設定を保存しました: {st.session_state['save_success']}", icon="✅")
        del st.session_state['save_success']
    
    if 'load_success' in st.session_state:
        st.success("設定を読み込みました", icon="✅")
        del st.session_state['load_success']
    
    if 'delete_success' in st.session_state:
        st.success("設定ファイルを削除しました", icon="✅")
        del st.session_state['delete_success']

# 共通設定
with st.container(border=True):
    st.header("⚙️ 共通設定")
    
    # 試験名、分析場所、Groupを横並びに表示
    test_col, location_col, group_col = st.columns([2, 2, 2])
    
    with test_col:
        st.markdown("**試験名を入力**")
        test_name = st.text_input("試験名を入力", value="試験_001", key="test_name_input_common", label_visibility="collapsed")
    
    with location_col:
        st.markdown("**分析場所を選択**")
        analysis_location = st.radio("分析場所を選択", ["東分析", "西分析"], horizontal=True, index=0, key="analysis_location_common", label_visibility="collapsed")
    
    with group_col:
        # 分析場所に応じてCSVファイルを読み込み
        if analysis_location == "東分析":
            calibration_df = read_csv_anti("Calibration_upper_limit_OES.csv")
        else:
            calibration_df = read_csv_anti("Calibration_upper_limit_XRF.csv")
        
        # Group列をセレクトボックスで選択
        if not calibration_df.empty and 'Group' in calibration_df.columns:
            group_options = calibration_df['Group'].dropna().unique().tolist()
            default_index = 0 if group_options else 0
            st.markdown("**Groupを選択してください**")
            selected_group = st.selectbox(
                "Groupを選択してください",
                options=group_options,
                index=default_index,
                key="selected_group_common",
                label_visibility="collapsed"
            )
        else:
            selected_group = None
            st.warning("キャリブレーションファイルの読み込みに失敗しました。")
    
    # 選択したグループの成分を表示
    if selected_group and not calibration_df.empty:
        group_data = calibration_df[calibration_df['Group'] == selected_group]
        if not group_data.empty:
            # 成分列を取得（Group列以外で値がある列）
            component_cols = [col for col in calibration_df.columns if col != 'Group']
            display_data = {}
            for col in component_cols:
                val = group_data[col].iloc[0]
                if pd.notna(val) and val != 0 and str(val).strip() != '':
                    display_data[col] = val
            
            if display_data:
                st.markdown("**検量線上限値**")
                display_df = pd.DataFrame([display_data])
                display_df.index = [selected_group]
                st.dataframe(display_df, use_container_width=True)

# --- 5つの配合タブを作成 ---
# レスポンシブ対応CSS
st.markdown("""
<style>
/* タブの文字に枠線を追加 */
.stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
    border: 1px solid #FF8C00;
    border-radius: 8px;
    padding: 5px 10px;
    background-color: transparent;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] [data-testid="stMarkdownContainer"] p {
    background-color: #e6f3ff;
    border: 3px solid #FF8C00;
}

/* レスポンシブ対応 */
@media screen and (max-width: 1024px) {
    .stColumns > div {
        min-width: 0 !important;
        flex: 1 1 auto !important;
    }
    .stSelectbox > div > div {
        min-width: 0 !important;
    }
    .stNumberInput > div > div {
        min-width: 0 !important;
    }
    .stMultiSelect > div > div {
        min-width: 0 !important;
    }
}

/* iPad縦向け対応 */
@media screen and (max-width: 768px) {
    .stColumns {
        flex-direction: column !important;
    }
    .stColumns > div {
        width: 100% !important;
        margin-bottom: 1rem;
    }
}

/* ラベルとインプットボックスの縦方向中央揃え */
.stColumns > div > div {
    display: flex;
    align-items: center;
    min-height: 2.5rem;
}
.stMarkdown p {
    margin: 0;
    display: flex;
    align-items: center;
    height: 2.5rem;
}

/* テーブルのレスポンシブ対応 */
@media screen and (max-width: 1024px) {
    .stDataFrame {
        overflow-x: auto;
    }
}
</style>
""", unsafe_allow_html=True)

tab_names = [f"🧪 Ch{i+1}" for i in range(5)] + ["📝 指示票", "📈 分析依頼票"]
tabs = st.tabs(tab_names)

# blending_ratio.csvから目標成分を読み込む
def read_blending_ratio():
    try:
        df = pd.read_csv("blending_ratio.csv", encoding='cp932', index_col=0)
        return df
    except Exception as e:
        st.error(f"blending_ratio.csvの読み込みに失敗: {e}")
        return pd.DataFrame()

blending_ratio_df = read_blending_ratio()

# PDF生成関数
def generate_instruction_pdf(test_name, multiplier=0.95):
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.styles import ParagraphStyle
        
        # 日本語フォントを登録
        try:
            pdfmetrics.registerFont(TTFont('NotoSansCJK', 'NotoSansCJK-Regular.ttf'))
            font_name = 'NotoSansCJK'
        except:
            try:
                pdfmetrics.registerFont(TTFont('MSGothic', 'msgothic.ttc'))
                font_name = 'MSGothic'
            except:
                font_name = 'Helvetica'
        
        from reportlab.lib.pagesizes import landscape
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=20, rightMargin=20)
        styles = getSampleStyleSheet()
        story = []
        
        # タイトルスタイル
        title_style = ParagraphStyle('JapaneseTitle', parent=styles['Title'], fontName=font_name, fontSize=12)
        
        # 各チャンネルを個別のセクションとして表示
        valid_channels = []
        for i in range(5):
            app_c_value = st.session_state.get(f"target_C_{i}", 0.0)
            if app_c_value > 0:
                valid_channels.append(i)
        
        if valid_channels:
            # タイトル
            title = Paragraph(f"指示票 - {test_name}", title_style)
            story.append(title)
            story.append(Spacer(1, 10))
            
            # 全てのチャンネルを1行に表示
            channel_tables = []
            
            for i in valid_channels:
                    # チャンネル見出し
                    ch_style = ParagraphStyle('ChannelHeader', parent=styles['Heading3'], fontName=font_name, fontSize=12, alignment=1)
                    ch_header = Paragraph(f"Ch{i+1}", ch_style)
                    
                    # 基本情報
                    total_weight_kg = st.session_state.get(f"total_weight_{i}", 110.0)
                    remaining_weight_kg = st.session_state.get(f"remaining_weight_{i}", 0.0)
                    mode = st.session_state.get(f"mode_radio_{i}", "FCD")
                    tapping_temp = st.session_state.get(f"tapping_temp_{i}", 1450)
                    
                    # 基本情報テーブル
                    basic_data = [
                        ["溶湯重量", f"{total_weight_kg}kg"],
                        ["残湯量", f"{remaining_weight_kg}kg"],
                        ["溶湯種別", mode],
                        ["出湯温度", f"{tapping_temp}℃"]
                    ]
                    
                    basic_table = Table(basic_data, colWidths=[50, 50])
                    basic_table.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey)
                    ]))
                    
                    # 材料データ
                    base_material_names = ["神鋼SP銑", "故銑", "鋼屑"]
                    selected_materials = st.session_state.get(f"selected_materials_widget_{i}", [])
                    calc_results = st.session_state.get(f"calc_results_{i}", {})
                    
                    material_data = []
                    for mat in base_material_names:
                        if mat in selected_materials and mat in calc_results and calc_results[mat] > 0:
                            adjusted_weight = calc_results[mat] * multiplier
                            material_data.append([mat, f"{round(adjusted_weight/1000)}kg", "□"])
                    
                    material_table = None
                    if material_data:
                        material_title = Paragraph("材料", ParagraphStyle('SectionTitle', parent=styles['Normal'], fontName=font_name, fontSize=10, spaceAfter=3))
                        material_table = Table(material_data, colWidths=[60, 60, 20])
                        material_table.setStyle(TableStyle([
                            ('FONTNAME', (0, 0), (-1, -1), font_name),
                            ('FONTSIZE', (0, 0), (-1, -1), 9),
                            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black)
                        ]))
                    
                    # 合金データ
                    alloy_data = []
                    for mat in selected_materials:
                        if mat not in base_material_names and mat in calc_results and calc_results[mat] > 0:
                            adjusted_weight = calc_results[mat] * multiplier
                            alloy_data.append([mat, f"{int(adjusted_weight):,}g", "□"])
                    
                    alloy_table = None
                    if alloy_data:
                        alloy_title = Paragraph("合金", ParagraphStyle('SectionTitle', parent=styles['Normal'], fontName=font_name, fontSize=10, spaceAfter=3))
                        alloy_table = Table(alloy_data, colWidths=[60, 60, 20])
                        alloy_table.setStyle(TableStyle([
                            ('FONTNAME', (0, 0), (-1, -1), font_name),
                            ('FONTSIZE', (0, 0), (-1, -1), 9),
                            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black)
                        ]))
                    
                    # 添加剤データ
                    selected_additives = st.session_state.get(f"selected_additives_{i}", [])
                    total_weight = st.session_state.get(f"total_weight_{i}", 110.0) * 1000
                    
                    additive_data = []
                    for j, additive in enumerate(selected_additives):
                        percent_key = f"additive_percent_{additive}_{i}_{j}"
                        if percent_key in st.session_state:
                            percent = st.session_state[percent_key]
                            grams = percent / 100 * total_weight
                            if grams > 0:
                                additive_data.append([additive, f"{int(grams):,}g", "□"])
                    
                    additive_table = None
                    if additive_data:
                        additive_title = Paragraph("添加剤", ParagraphStyle('SectionTitle', parent=styles['Normal'], fontName=font_name, fontSize=10, spaceAfter=3))
                        additive_table = Table(additive_data, colWidths=[60, 60, 20])
                        additive_table.setStyle(TableStyle([
                            ('FONTNAME', (0, 0), (-1, -1), font_name),
                            ('FONTSIZE', (0, 0), (-1, -1), 9),
                            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black)
                        ]))
                    
                    # 全てのテーブルを結合
                    channel_elements = [basic_table, Spacer(1, 8)]
                    if material_table:
                        channel_elements.extend([material_title, material_table, Spacer(1, 8)])
                    if alloy_table:
                        channel_elements.extend([alloy_title, alloy_table, Spacer(1, 8)])
                    if additive_table:
                        channel_elements.extend([additive_title, additive_table])
                    
                    # ヘッダーとコンテンツを組み合わせ
                    channel_content = [[ch_header]]
                    for element in channel_elements:
                        channel_content.append([element])
                    
                    channel_wrapper = Table(channel_content, colWidths=[130])
                    channel_wrapper.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 8),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                        ('TOPPADDING', (0, 0), (-1, -1), 2),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 2)
                    ]))
                    
                    channel_tables.append(channel_wrapper)
                
            # 全チャンネルを横並びに配置
            if len(channel_tables) == 1:
                story.append(channel_tables[0])
            else:
                row_table = Table([channel_tables], colWidths=[160] * len(channel_tables))
                row_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 15),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 15)
                ]))
                story.append(row_table)
        
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        st.error(f"PDF生成エラー: {e}")
        return None

for tab_idx, tab in enumerate(tabs):
    with tab:
        if tab_idx == 5:  # 指示票タブの場合
            st.markdown(f"<h2 style='text-align: center; background-color: #ffe6e6; padding: 10px; border-radius: 5px;'>{tab_names[tab_idx]}</h2>", unsafe_allow_html=True)
        elif tab_idx == 6:  # 分析依頼票タブの場合
            st.markdown(f"<h2 style='text-align: center; background-color: #f0f0f0; padding: 10px; border-radius: 5px;'>{tab_names[tab_idx]}</h2>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h2 style='text-align: center; background-color: #e6f3ff; padding: 10px; border-radius: 5px;'>{tab_names[tab_idx]}</h2>", unsafe_allow_html=True)
        
        # 新しいタブの処理
        if tab_idx >= 5:  # 指示票、分析依頼票タブ
            if tab_idx == 5:  # 指示票
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("**設定倍率（材料、合金の添加量に反映）**")
                multiplier = st.number_input("設定倍率", min_value=0.1, max_value=2.0, value=0.95, step=0.01, key="pdf_multiplier", label_visibility="collapsed")
                
                if st.button("📁 指示票PDFを保存", key="pdf_save"):
                    pdf_buffer = generate_instruction_pdf(test_name, multiplier)
                    if pdf_buffer:
                        # デスクトップアプリ用にファイルを直接保存
                        pdf_filename = f"{test_name}_指示票.pdf"
                        try:
                            with open(pdf_filename, 'wb') as f:
                                f.write(pdf_buffer.getvalue())
                            st.success(f"PDFファイルを保存しました: {pdf_filename}")
                        except Exception as e:
                            st.error(f"PDF保存エラー: {e}")
                            # フォールバックとしてダウンロードボタンを表示
                            st.download_button(
                                label="📁 指示票PDFをダウンロード",
                                data=pdf_buffer.getvalue(),
                                file_name=pdf_filename,
                                mime="application/pdf",
                                key="pdf_download_fallback"
                            )
                
                # blending_ratio.csvから値がすべて0でない配合を取得
                if blending_ratio_df is not None and not blending_ratio_df.empty:
                    instruction_data = []
                    base_materials_data = []  # 神鋼SP銑、故銑、鋼屑のみのデータ
                    
                    for i in range(5):  # Ch1-5をチェック
                        blend_name = f"Ch{i+1}"
                        if blend_name in blending_ratio_df.index:
                            blend_row = blending_ratio_df.loc[blend_name]
                            # アプリでの入力値（C）が0でないかチェック
                            app_c_value = st.session_state.get(f"target_C_{i}", 0.0)
                            has_nonzero = app_c_value > 0
                            if has_nonzero:
                                # セッションステートから実際の計算結果を取得
                                materials_info = {"配合名": blend_name}
                                base_materials_info = {"配合名": blend_name}
                                
                                # 溶解重量を取得
                                total_weight = st.session_state.get(f"total_weight_{i}", 110.0) * 1000
                                
                                # 添加剤の必要添加量を取得（g単位）
                                selected_additives = st.session_state.get(f"selected_additives_{i}", [])
                                for j, additive in enumerate(selected_additives):
                                    percent_key = f"additive_percent_{additive}_{i}_{j}"
                                    if percent_key in st.session_state:
                                        percent = st.session_state[percent_key]
                                        grams = percent / 100 * total_weight
                                        materials_info[f"{additive}(g)"] = int(grams)
                                    else:
                                        materials_info[f"{additive}(g)"] = 0
                                
                                # 選択された材料の必要添加量を取得（計算結果から）
                                selected_materials = st.session_state.get(f"selected_materials_widget_{i}", [])
                                calc_results = st.session_state.get(f"calc_results_{i}", {})
                                
                                # 神鋼SP銑、故銑、鋼屑の重量のみを記録
                                base_material_names = ["神鋼SP銑", "故銑", "鋼屑"]
                                for mat in base_material_names:
                                    if mat in selected_materials and mat in calc_results:
                                        weight_g = calc_results[mat]
                                        if weight_g > 0:  # 重量0gは表示しない
                                            base_materials_info[f"{mat}(g)"] = int(weight_g)
                                
                                # その他の材料
                                for mat in selected_materials:
                                    if mat not in ["鋼屑", "神鋼ＳＰ銑", "故銑"]:
                                        # 計算結果から実際の値を取得
                                        if mat in calc_results:
                                            materials_info[f"{mat}(g)"] = int(calc_results[mat])
                                        else:
                                            materials_info[f"{mat}(g)"] = 0
                                
                                instruction_data.append(materials_info)
                                base_materials_data.append(base_materials_info)
                    
                    # 有効な配合を収集
                    valid_blends = []
                    for i in range(5):
                        blend_name = f"Ch{i+1}"
                        if blend_name in blending_ratio_df.index:
                            blend_row = blending_ratio_df.loc[blend_name]
                            has_nonzero = any(pd.notna(v) and v != 0 for v in blend_row.values)
                            if has_nonzero:
                                valid_blends.append(i)
                    
                    # 5列固定で表示
                    cols = st.columns(5)
                    for i in range(5):
                        with cols[i]:
                            blend_name = f"Ch{i+1}"
                            if blend_name in blending_ratio_df.index:
                                blend_row = blending_ratio_df.loc[blend_name]
                                app_c_value = st.session_state.get(f"target_C_{i}", 0.0)
                                has_nonzero = app_c_value > 0
                                if has_nonzero:
                                    with st.container(border=True):
                                        st.markdown(f"<h3 style='text-align: center; background-color: #e6f3ff; padding: 8px; border-radius: 5px; margin-bottom: 10px;'>Ch{i+1}</h3>", unsafe_allow_html=True)
                                        
                                        # 基本情報を表形式で表示
                                        total_weight_kg = st.session_state.get(f"total_weight_{i}", 110.0)
                                        remaining_weight_kg = st.session_state.get(f"remaining_weight_{i}", 0.0)
                                        mode = st.session_state.get(f"mode_radio_{i}", "FCD")
                                        tapping_temp = st.session_state.get(f"tapping_temp_{i}", 1450)
                                        
                                        basic_info = pd.DataFrame({
                                            "設定値": [f"{total_weight_kg}kg", f"{remaining_weight_kg}kg", mode, f"{tapping_temp}℃"]
                                        }, index=["溶湯重量", "残湯量", "溶湯種別", "出湯温度"])
                                        st.dataframe(basic_info, use_container_width=True, hide_index=False)
                                        
                                        st.markdown("---")
                                        
                                        # 神鋼SP銑、故銑、鋼屑のデータを取得（kg単位に変換）
                                        base_data = base_materials_data[i] if i < len(base_materials_data) else {}
                                        if len(base_data) > 1:
                                            st.markdown("**材料**")
                                            base_data_kg = {k.replace("(g)", ""): round(v/1000) for k, v in base_data.items() if k != "配合名"}
                                            base_df = pd.DataFrame([base_data_kg]).T
                                            base_df.columns = ["添加量（kg）"]
                                            st.dataframe(base_df, use_container_width=True, hide_index=False)
                                        
                                        # その他の材料と添加剤を取得
                                        all_data = instruction_data[i] if i < len(instruction_data) else {}
                                        selected_additives = st.session_state.get(f"selected_additives_{i}", [])
                                        base_material_names = ["神鋼SP銑", "故銑", "鋼屑"]
                                        
                                        # 材料データと添加剤データを分離
                                        material_info = {}
                                        additive_info = {}
                                        
                                        for key, value in all_data.items():
                                            if key != "配合名":
                                                if key.endswith("(g)") and not any(additive in key for additive in selected_additives) and not any(base_mat in key for base_mat in base_material_names):
                                                    material_info[key.replace("(g)", "")] = value
                                                elif key.endswith("(g)") and any(additive in key for additive in selected_additives):
                                                    additive_info[key.replace("(g)", "")] = value
                                        
                                        if material_info:
                                            st.markdown("**合金**")
                                            materials_df = pd.DataFrame([material_info]).T
                                            materials_df.columns = ["添加量（g）"]
                                            st.dataframe(materials_df, use_container_width=True, hide_index=False)
                                        
                                        if additive_info:
                                            st.markdown("---")
                                            st.markdown("**添加剤**")
                                            additives_df = pd.DataFrame([additive_info]).T
                                            additives_df.columns = ["添加量（g）"]
                                            st.dataframe(additives_df, use_container_width=True, hide_index=False)
                    
                    if not any(st.session_state.get(f"target_C_{i}", 0.0) > 0 for i in range(5)):
                        st.info("表示する配合データがありません。")
                else:
                    st.warning("blending_ratio.csvが読み込まれていません。")
            elif tab_idx == 6:  # 分析依頼票
                st.markdown("📈 **分析依頼票の内容をここに表示します**")
                st.info("分析依頼票の機能は開発中です。")
            continue
        
        # タブインデックスを保存（他の場所でidxが使われるため）
        current_tab_index = tab_idx
        
        # Session Stateの初期化
        if f"total_weight_{current_tab_index}" not in st.session_state:
            st.session_state[f"total_weight_{current_tab_index}"] = 110.0
        if f"remaining_weight_{current_tab_index}" not in st.session_state:
            st.session_state[f"remaining_weight_{current_tab_index}"] = 0.0
        if f"tapping_temp_{current_tab_index}" not in st.session_state:
            st.session_state[f"tapping_temp_{current_tab_index}"] = 1450
        # blending_ratio.csvから目標値を取得
        blend_row = None
        if blending_ratio_df is not None and f"Ch{current_tab_index+1}" in blending_ratio_df.index:
            blend_row = blending_ratio_df.loc[f"Ch{current_tab_index+1}"]
        # 以降、全てのstウィジェットのkeyに f"_{current_tab_index}" を付与して、タブごとに独立させる
        # ---------------------------
        # 基本設定
        # ---------------------------
        with st.container(border=True):
            st.header("⚙️ 基本設定")
            weight_col1, weight_col2, mode_col, temp_col = st.columns(4)
            with weight_col1:
                st.markdown("**溶解重量 (kg)**")
                if f"total_weight_{current_tab_index}" not in st.session_state:
                    st.session_state[f"total_weight_{current_tab_index}"] = 110.0
                total_weight_kg = st.number_input("溶解重量 (kg)", min_value=1.0, key=f"total_weight_{current_tab_index}", label_visibility="collapsed")
            with weight_col2:
                st.markdown("**残湯量 (kg)**")
                if f"remaining_weight_{current_tab_index}" not in st.session_state:
                    st.session_state[f"remaining_weight_{current_tab_index}"] = 0.0
                remaining_weight_kg = st.number_input("残湯量 (kg)", min_value=0.0, key=f"remaining_weight_{current_tab_index}", label_visibility="collapsed")
            with mode_col:
                st.markdown("**溶湯種別選択**")
                mode = st.radio("溶湯種別選択", ["FCD", "FC"], horizontal=True, index=0, key=f"mode_radio_{current_tab_index}", label_visibility="collapsed")
            with temp_col:
                st.markdown("**出湯温度（℃）**")
                if f"tapping_temp_{current_tab_index}" not in st.session_state:
                    st.session_state[f"tapping_temp_{current_tab_index}"] = 1450
                tapping_temp = st.number_input("出湯温度（℃）", min_value=1300, max_value=1600, step=1, key=f"tapping_temp_{current_tab_index}", label_visibility="collapsed")
        total_weight_g = total_weight_kg * 1000

        # ---------------------------
        # 目標成分
        # ---------------------------
        with st.container(border=True):
            st.header("🎯 目標成分")
            
            default_targets = {"C": 3.6, "Si": 2.4, "Mn": 0.4}
            # blending_ratio.csvから成分値を取得
            blend_targets = {}
            blend_tolerance_types = {}  # 判定方法を保存
            if blend_row is not None:
                for e in elements:
                    v = blend_row.get(e, 0.0)
                    tolerance_type = "±"  # デフォルトは±
                    try:
                        if isinstance(v, str) and v.startswith('<'):
                            # "<0.02"のような形式の場合
                            v = float(v[1:])  # "<"を除いて数値に変換
                            tolerance_type = "以下"  # 判定方法を"以下"に設定
                        else:
                            v = float(v)
                    except Exception:
                        v = 0.0
                    blend_targets[e] = v
                    blend_tolerance_types[e] = tolerance_type
            # blending_ratio.csvの値をそのまま使用（デフォルト値は使わない）
            
            # blending_ratio.csvで0以外が入力されている成分を自動で追加
            blend_nonzero_elements = [e for e in elements if blend_targets.get(e, 0.0) not in (0, None) and not pd.isna(blend_targets.get(e, 0.0))]
            # デフォルトは0以外の成分すべて（なければC,Si,Mn）
            default_elements = blend_nonzero_elements[:]
            if not default_elements:
                default_elements = [e for e in ["C", "Si", "Mn"] if blend_targets.get(e, 0.0) != 0]
                if not default_elements:
                    default_elements = ["C", "Si", "Mn"]
            
            state_key = f"selected_elements_{current_tab_index}"
            # セッションステートに未設定、または空リストなら初期化
            if state_key not in st.session_state or st.session_state[state_key] == []:
                st.session_state[state_key] = default_elements

            st.markdown("**元素選択**")
            selected_elements = st.multiselect(
                "成分調整する元素を選択してください（複数可）",
                options=elements,
                key=state_key,
                label_visibility="collapsed"
            )
            
            target_composition = {}
            tolerance_values = {}
            tolerance_types = {}
            user_c_input = None
            
            # 選択された元素の設定を表示
            if selected_elements:
                st.markdown("**目標値**")
                # 元素を5列表示
                element_cols = st.columns(min(5, len(selected_elements)))
                for i, e in enumerate(selected_elements):
                    col = element_cols[i % len(element_cols)]
                    with col:
                        # Cの場合は自動加算後の値をタイトルに表示
                        if e == "C":
                            default_val = blend_targets.get(e, default_targets.get(e, 0.0))
                            # 一時的に計算してタイトル用の値を取得
                            if mode == "FCD":
                                calc_val_for_title = default_val + 0.07
                            else:
                                calc_val_for_title = default_val + 0.05
                            expander_title = f"⚙️ {e}（自動加算後: {calc_val_for_title:.2f}%）"
                        else:
                            expander_title = f"⚙️ {e}"
                        
                        with st.expander(expander_title, expanded=True):
                            # blending_ratio.csv優先、なければデフォルト
                            default_val = blend_targets.get(e, default_targets.get(e, 0.0))
                            
                            if e == "C":
                                target_label_col, target_input_col = st.columns([1, 1])
                                with target_label_col:
                                    st.markdown("**目標値（%）**")
                                with target_input_col:
                                    if f"target_{e}_{current_tab_index}" not in st.session_state:
                                        st.session_state[f"target_{e}_{current_tab_index}"] = default_val
                                    user_val = st.number_input(f"目標値（%）", min_value=0.0, key=f"target_{e}_{current_tab_index}", label_visibility="collapsed")
                                user_c_input = user_val
                                if mode == "FCD":
                                    calc_val = user_val + 0.07
                                else:
                                    calc_val = user_val + 0.05
                                target_composition[e] = calc_val
                            else:
                                target_label_col, target_input_col = st.columns([1, 1])
                                with target_label_col:
                                    st.markdown("**目標値（%）**")
                                with target_input_col:
                                    if f"target_{e}_{current_tab_index}" not in st.session_state:
                                        st.session_state[f"target_{e}_{current_tab_index}"] = default_val
                                    target_composition[e] = st.number_input(f"目標値（%）", min_value=0.0, key=f"target_{e}_{current_tab_index}", label_visibility="collapsed")
                            
                            default_tol = 0.05 if e in ["C", "Si", "Mn"] else 0.01
                            tol_label_col, tol_input_col = st.columns([1, 1])
                            with tol_label_col:
                                st.markdown("**許容値**")
                            with tol_input_col:
                                if f"tol_{e}_{current_tab_index}" not in st.session_state:
                                    st.session_state[f"tol_{e}_{current_tab_index}"] = default_tol
                                tolerance_values[e] = st.number_input(f"許容値", min_value=0.0, step=0.01, key=f"tol_{e}_{current_tab_index}", label_visibility="collapsed")
                            
                            type_label_col, type_input_col = st.columns([1, 1])
                            with type_label_col:
                                st.markdown("**判定方法**")
                            with type_input_col:
                                default_tol_type = blend_tolerance_types.get(e, "±")
                                if f"tol_type_{e}_{current_tab_index}" not in st.session_state:
                                    st.session_state[f"tol_type_{e}_{current_tab_index}"] = default_tol_type
                                tolerance_types[e] = st.selectbox(f"判定方法", ["±", "以下"], key=f"tol_type_{e}_{current_tab_index}", label_visibility="collapsed")
            
            # 選択されていないものは0
            for e in elements:
                if e not in selected_elements:
                    target_composition[e] = 0.0
                    tolerance_values[e] = 0.01
                    tolerance_types[e] = blend_tolerance_types.get(e, "±")
            
            # Feの目標値は100%から他元素の合計を引いた値
            fe_target = 100.0 - sum(target_composition.values())
            target_composition['Fe'] = fe_target

        # ---------------------------
        # 添加剤設定
        # ---------------------------
        with st.container(border=True):
            st.header("🧪 添加剤設定")
            additive_list = list(additives_df.index)
            # FCD/FCモードで初期選択を切り替え
            if mode == "FCD":
                default_additives = [a for a in additive_list if a in ["OGRC-4.5H", "SカバーM"]]
            else:
                default_additives = []
            st.markdown("**添加剤選択**")
            if f"selected_additives_{current_tab_index}" not in st.session_state:
                st.session_state[f"selected_additives_{current_tab_index}"] = default_additives
            selected_additives = st.multiselect(
                "添加材として使用するものを選択してください（複数可）",
                options=additive_list,
                key=f"selected_additives_{current_tab_index}",
                label_visibility="collapsed"
            )
            
            additive_default_targets = {"OGRC-4.5H": 1.3, "SカバーM": 0.8}
            additive_inputs_percent = {}
            additive_inputs_grams = {}
            
            if selected_additives:
                st.markdown("**選択された添加剤**")
                cols = st.columns(min(5, len(selected_additives)))
                # 選択順に左詰めで表示
                for i, additive in enumerate(selected_additives):
                    col = cols[i % len(cols)]
                    default_val = additive_default_targets.get(additive, 0.0)
                    if f"additive_percent_{additive}_{current_tab_index}_{i}" not in st.session_state:
                        st.session_state[f"additive_percent_{additive}_{current_tab_index}_{i}"] = default_val
                    percent = col.number_input(
                        f"{additive}（%）",
                        min_value=0.0,
                        max_value=100.0,
                        key=f"additive_percent_{additive}_{current_tab_index}_{i}"
                    )
                    additive_inputs_percent[additive] = percent
                    grams = percent / 100 * total_weight_g
                    additive_inputs_grams[additive] = grams
            
            # 選択されていないものは0
            for additive in additive_list:
                if additive not in selected_additives:
                    additive_inputs_percent[additive] = 0.0
                    additive_inputs_grams[additive] = 0.0

        # ---------------------------
        # 添加材の元素合計
        # ---------------------------
        additive_contributions = {e: 0.0 for e in elements + ['Fe']}
        for additive, weight_g in additive_inputs_grams.items():
            for e in elements + ['Fe']:
                percent = additives_df.at[additive, e] if e in additives_df.columns else 0.0
                # NaNやSeries対応
                try:
                    percent = float(percent)
                except Exception:
                    percent = 0.0
                if np.isnan(percent):
                    percent = 0.0
                additive_contributions[e] += weight_g * percent / 100  # gベース

        # 添加材によって供給された元素を % に変換（残り必要量計算のため）
        additive_composition_pct = {
            e: float(additive_contributions[e]) / total_weight_g * 100 for e in elements + ['Fe']
        }

        # ---------------------------
        # 残り必要な成分量（目標値 － 添加材由来）
        # ---------------------------
        required_composition = {
            e: max(0.0, target_composition[e] - additive_composition_pct[e]) for e in elements + ['Fe']
        }
        
        # 検量線上限値を取得
        calibration_limits = {}
        if selected_group and not calibration_df.empty:
            group_data = calibration_df[calibration_df['Group'] == selected_group]
            if not group_data.empty:
                for e in elements + ['Fe']:
                    if e in calibration_df.columns:
                        val = group_data[e].iloc[0]
                        if pd.notna(val) and val != 0:
                            calibration_limits[e] = float(val)
        
        # 成分目標値が検量線上限値を超える場合の処理
        urgent_analysis_target = {}
        post_analysis_addition = {}
        for e in elements + ['Fe']:
            # 入力された成分目標値で添加材の計算を行う
            original_target = target_composition[e] - additive_composition_pct[e]
            original_target = max(0.0, original_target)
            
            if e in calibration_limits and original_target > calibration_limits[e]:
                urgent_analysis_target[e] = calibration_limits[e]
                post_analysis_addition[e] = original_target - calibration_limits[e]
            else:
                urgent_analysis_target[e] = original_target
                post_analysis_addition[e] = 0.0

        # ---------------------------
        # 材料配合
        # ---------------------------
        with st.container(border=True):
            st.header("🧮 材料配合")
            
            # multiselectで材料選択
            all_materials = list(materials_df.index)
            init_materials = [m for m in all_materials if m in ["神鋼SP銑", "C粉", "Fe-Si", "Fe-Mn"]]
            if f"selected_materials_widget_{current_tab_index}" not in st.session_state:
                st.session_state[f"selected_materials_widget_{current_tab_index}"] = init_materials
            selected_materials = st.multiselect(
                "使用する材料を選択してください",
                options=all_materials,
                key=f"selected_materials_widget_{current_tab_index}",
                label_visibility="collapsed"
            )

            # 材料ごとの必要添加量による成分増加量の表を表示
            if selected_materials:
                mat_elements_disp = [e for e in elements + ['Fe'] if e in materials_df.columns]
                # 必要添加量（g）を取得（計算前は0になるので、計算後のadd_weightsを使う）
                # ここでは、add_weightsが計算される前なので、下の計算後に表示するのが正しい
                pass  # 表示は下のadd_weights計算後に移動

            if len(selected_materials) == 0:
                st.warning("1つ以上の材料を選択してください。")
            else:
                # 材料名リスト
                material_names = selected_materials
                # 鋼屑・神鋼SP銑・故銑の手動入力欄を作成
                manual_input_dict = {}
                manual_materials = [m for m in ["鋼屑", "神鋼SP銑", "故銑"] if m in material_names]
                if manual_materials:
                    st.markdown("**材料配合（kg）** <span style='color:red'>・0（入力なし）で自動配合</span>", unsafe_allow_html=True)
                    manual_cols = st.columns(min(3, len(manual_materials)))
                    for mat_idx, mat in enumerate(manual_materials):
                        col_idx = mat_idx % len(manual_cols)
                        if f"manual_{mat}_{current_tab_index}" not in st.session_state:
                            st.session_state[f"manual_{mat}_{current_tab_index}"] = 0.0
                        manual_input_kg = manual_cols[col_idx].number_input(f"{mat}（kg）", min_value=0.0, step=0.1, key=f"manual_{mat}_{current_tab_index}")
                        manual_input_dict[mat] = manual_input_kg * 1000
                # 元素リスト（Fe含む）
                mat_elements = [e for e in elements + ['Fe'] if e in materials_df.columns]
                # 材料ごとの手動指定値
                manual_values = [manual_input_dict.get(m, 0.0) for m in material_names]
                # 自動計算対象のインデックス
                auto_idx = [i for i, m in enumerate(material_names) if m not in manual_input_dict or manual_input_dict[m] == 0.0]
                # 手動指定対象のインデックス
                manual_idx = [i for i, m in enumerate(material_names) if m in manual_input_dict and manual_input_dict[m] > 0.0]
                # A: 材料成分行列（各材料ごとに各元素の%） shape=(元素数, 材料数)
                A_full = materials_df.loc[material_names, mat_elements].T.values / 100  # %→fraction
                # b: 必要成分量（g） shape=(元素数,) - 至急分析目標値を使用
                b_full = np.array([urgent_analysis_target[e] / 100 * total_weight_g for e in mat_elements])
                # 手動指定分をbから引く
                b = b_full.copy()
                if manual_idx:
                    for j, m_idx in enumerate(manual_idx):
                        b -= A_full[:, m_idx] * manual_values[m_idx]

                # --- ここから下を常に表示する ---
                show_tables = True
                add_weights = None
                if auto_idx:
                    A_auto = A_full[:, auto_idx]
                    # 安全な最小二乗法で解く
                    try:
                        # まず通常の最小二乗法を試行
                        x_unconstrained, residuals, rank, s = np.linalg.lstsq(A_auto, b, rcond=1e-10)
                        x_constrained = np.maximum(x_unconstrained, 0)  # 負の値を0にクリップ
                        add_weights = np.array(manual_values)
                        for i, idx in enumerate(auto_idx):
                            add_weights[idx] = x_constrained[i]
                        if rank < A_auto.shape[1]:
                            st.warning("行列のランク不足のため、近似解を使用しています。")
                    except Exception as e:
                        st.error(f"計算エラー: {str(e)}")
                        # フォールバック：単純な比例配分
                        total_needed = np.sum(np.abs(b))
                        if total_needed > 1e-10:
                            base_weight = 1000.0  # 1kgを基準
                            add_weights = np.array(manual_values)
                            for i, idx in enumerate(auto_idx):
                                add_weights[idx] = base_weight / len(auto_idx)
                        else:
                            add_weights = np.array(manual_values)
                else:
                    # 全て手動指定の場合
                    add_weights = np.array(manual_values)

                if add_weights is not None:
                    # 材料・添加材ごとの必要添加量による成分増加量の表を表示
                    mat_elements_disp = [e for e in elements + ['Fe'] if e in materials_df.columns]
                    add_weights_disp = add_weights
                    # 歩留まり列があれば取得、なければ1.0で埋める
                    if '歩留まり' in materials_df.columns:
                        yield_rates = materials_df.loc[material_names, '歩留まり'].fillna(1.0).astype(float)
                    else:
                        yield_rates = pd.Series(1.0, index=material_names)
                    mat_table = materials_df.loc[material_names, mat_elements_disp]
                    # 添加材も同じ形式でまとめる
                    additive_rows = []
                    for a in selected_additives:
                        grams = additive_inputs_grams[a]
                        row = {"必要添加量(g)": f"{int(round(grams)):,}"}
                        for e in mat_elements_disp:
                            val = additives_df.at[a, e] if e in additives_df.columns else 0.0
                            try:
                                val = float(val)
                            except Exception:
                                val = 0.0
                            if np.isnan(val):
                                val = 0.0
                            inc = val * grams / total_weight_g
                            row[e] = f"{inc:.3g}" if inc != 0 else "0"
                        additive_rows.append((a, row))
                    # 材料分
                    inc_table = pd.DataFrame(index=mat_table.index, columns=["必要添加量(g)"] + list(mat_table.columns))
                    for m in mat_table.index:
                        total_weight_for_material = add_weights_disp[material_names.index(m)]
                        inc_table.at[m, "必要添加量(g)"] = f"{int(round(total_weight_for_material)):,}"
                        y = yield_rates[m]
                        for e in mat_table.columns:
                            # 歩留まりを掛けて計算
                            inc = mat_table.at[m, e] * y * total_weight_for_material / total_weight_g
                            if inc == 0:
                                inc_table.at[m, e] = "0"
                            else:
                                inc_table.at[m, e] = f"{inc:.3g}"
                    # 添加材分を追加
                    for a, row in additive_rows:
                        inc_table.loc[a] = row
                    # 合計行を追加
                    sum_row = {"必要添加量(g)": "-"}
                    total_weight_sum = 0
                    for row_idx in inc_table.index:
                        weight_str = inc_table.at[row_idx, "必要添加量(g)"]
                        try:
                            weight_val = float(weight_str.replace(",", ""))
                            total_weight_sum += weight_val
                        except Exception:
                            pass
                    sum_row["必要添加量(g)"] = f"{int(total_weight_sum):,}"
                    for e in mat_elements_disp:
                        vals = []
                        for row_idx in inc_table.index:
                            v = inc_table.at[row_idx, e]
                            try:
                                v = float(v.replace(",", ""))
                            except Exception:
                                v = 0.0
                            vals.append(v)
                        s = sum(vals)
                        sum_row[e] = f"{s:.3g}" if s != 0 else "0"
                    inc_table.loc["合計"] = sum_row
                    
                    # 選択した成分調整する元素に色を付ける
                    def highlight_selected_elements_urgent(row):
                        sel_color = "background-color: #ffe599"  # 薄い黄色
                        result = []
                        for col in row.index:
                            if col in selected_elements:
                                result.append(sel_color)
                            else:
                                result.append("")
                        return result
                    
                    # 成分の値がすべて0の列を非表示
                    cols_to_show = ["必要添加量(g)"]
                    for e in mat_elements_disp:
                        if float(sum_row[e]) != 0:
                            cols_to_show.append(e)
                    inc_table_filtered = inc_table[cols_to_show]
                
                    st.markdown("**成分増加量（%）（至急分析目標値）**")
                    st.dataframe(
                        inc_table_filtered.style.apply(highlight_selected_elements_urgent, axis=1),
                        use_container_width=True
                    )
                    # 添加する添加材だけ表示
                    # 0gでない、かつ選択されている添加材のみ抽出
                    used_additives = [a for a in selected_additives if additive_inputs_grams[a] > 0]
                    # ユニークな列名（重複対策）
                    unique_additive_list = []
                    seen = {}
                    for name in used_additives:
                        if name not in seen:
                            unique_additive_list.append(name)
                            seen[name] = 1
                        else:
                            seen[name] += 1
                            unique_additive_list.append(f"{name}_{seen[name]}")
                    additives_grams_list = [additive_inputs_grams[a] for a in used_additives]
                    additives_df_disp = None  # 初期化
                    if unique_additive_list:
                        additives_df_disp = pd.DataFrame([additives_grams_list], columns=unique_additive_list)
                        additives_df_disp.index = ["必要添加量(g)"]
                        additives_df_disp_str = additives_df_disp.map(lambda x: f"{int(x):,}" if x != 0 else "0")
                        st.markdown("**添加材ごとの必要添加量（g）**")
                        # 列幅を文字数に合わせてフィット
                        col_widths = {c: st.column_config.Column(width=f"{max(80, len(str(c))*16)}px") for c in additives_df_disp_str.columns}
                        st.dataframe(additives_df_disp_str, use_container_width=True, hide_index=False, column_config=col_widths)
                    else:
                        st.markdown("**添加材ごとの必要添加量（g）**")
                        st.write("（選択・入力された添加材はありません）")

                    # 1e-3g以下は0として扱う
                    add_weights_masked = np.where(add_weights > 1e-3, add_weights, 0.0)
                # 材料名を列、必要添加量を値とした1行の表にする（小数点以下四捨五入）
                rounded_weights = np.round(add_weights)
                result_df = pd.DataFrame([rounded_weights], columns=material_names)
                result_df = result_df.loc[:, result_df.iloc[0] > 1e-3]  # 1e-3g以下は非表示
                result_df.index = ["必要添加量(g)"]
                # 必要添加量の表をカンマ区切りで表示
                # 至急分析後添加量を計算（検量線超過成分を個別に計算）
                post_analysis_weights = np.zeros(len(material_names))
                
                # 検量線上限値が設定されている成分のみ個別処理
                for e in mat_elements:
                    if e in calibration_limits and required_composition[e] > calibration_limits[e] and auto_idx:
                        # この成分を最も多く含む材料のみを使用
                        element_idx = mat_elements.index(e)
                        best_material_idx = None
                        best_content = 0
                        
                        for i, auto_index in enumerate(auto_idx):
                            content = A_full[element_idx, auto_index]
                            if content > best_content:
                                best_content = content
                                best_material_idx = i
                        
                        if best_material_idx is not None and best_content > 0:
                            needed_amount = post_analysis_addition[e] / 100 * total_weight_g / best_content
                            post_analysis_weights[auto_idx[best_material_idx]] += needed_amount
                
                # 材料・添加材ごとの必要添加量による成分増加量の表を表示
                mat_elements_disp = [e for e in elements + ['Fe'] if e in materials_df.columns]
                # 至急分析前添加量と至急分析後添加量を足した値を使用
                total_weights = add_weights + post_analysis_weights
                add_weights_disp = total_weights
                
                # 歩留まり列があれば取得、なければ1.0で埋める
                if '歩留まり' in materials_df.columns:
                    yield_rates = materials_df.loc[material_names, '歩留まり'].fillna(1.0).astype(float)
                else:
                    yield_rates = pd.Series(1.0, index=material_names)
                mat_table = materials_df.loc[material_names, mat_elements_disp]
                # 添加材も同じ形式でまとめる
                additive_rows = []
                for a in selected_additives:
                    grams = additive_inputs_grams[a]
                    row = {"必要添加量(g)": f"{int(round(grams)):,}"}
                    for e in mat_elements_disp:
                        val = additives_df.at[a, e] if e in additives_df.columns else 0.0
                        try:
                            val = float(val)
                        except Exception:
                            val = 0.0
                        if np.isnan(val):
                            val = 0.0
                        inc = val * grams / total_weight_g
                        row[e] = f"{inc:.3g}" if inc != 0 else "0"
                    additive_rows.append((a, row))
                # 材料分
                inc_table = pd.DataFrame(index=mat_table.index, columns=["必要添加量(g)"] + list(mat_table.columns))
                for m in mat_table.index:
                    total_weight_for_material = add_weights_disp[material_names.index(m)]
                    inc_table.at[m, "必要添加量(g)"] = f"{int(round(total_weight_for_material)):,}"
                    y = yield_rates[m]
                    for e in mat_table.columns:
                        # 歩留まりを掛けて計算
                        inc = mat_table.at[m, e] * y * total_weight_for_material / total_weight_g
                        if inc == 0:
                            inc_table.at[m, e] = "0"
                        else:
                            inc_table.at[m, e] = f"{inc:.3g}"
                # 添加材分を追加
                for a, row in additive_rows:
                    inc_table.loc[a] = row
                # 合計行を追加
                sum_row = {"必要添加量(g)": "-"}
                total_weight_sum = 0
                for row_idx in inc_table.index:
                    weight_str = inc_table.at[row_idx, "必要添加量(g)"]
                    try:
                        weight_val = float(weight_str.replace(",", ""))
                        total_weight_sum += weight_val
                    except Exception:
                        pass
                sum_row["必要添加量(g)"] = f"{int(total_weight_sum):,}"
                for e in mat_elements_disp:
                    vals = []
                    for row_idx in inc_table.index:
                        v = inc_table.at[row_idx, e]
                        try:
                            v = float(v.replace(",", ""))
                        except Exception:
                            v = 0.0
                        vals.append(v)
                    s = sum(vals)
                    sum_row[e] = f"{s:.3g}" if s != 0 else "0"
                inc_table.loc["合計"] = sum_row
                

                
                # 結果表に2行を追加
                result_with_analysis = pd.DataFrame([
                    rounded_weights,
                    np.round(post_analysis_weights)
                ], columns=material_names, index=["至急分析前添加量(g)", "至急分析後添加量(g)"])
                result_with_analysis = result_with_analysis.loc[:, (result_with_analysis.iloc[0] > 1e-3) | (result_with_analysis.iloc[1] > 1e-3)]
                
                st.markdown("**材料ごとの必要添加量（g）**")
                result_with_analysis_str = result_with_analysis.copy()
                
                result_with_analysis_str = result_with_analysis_str.astype(object)
                for row in result_with_analysis_str.index:
                    for col in result_with_analysis_str.columns:
                        val = result_with_analysis_str.at[row, col]
                        if val != "-" and isinstance(val, (int, float, np.integer, np.floating)):
                            if row == "至急分析後添加量(g)" and val == 0:
                                result_with_analysis_str.at[row, col] = "-"
                            else:
                                result_with_analysis_str.at[row, col] = f"{int(val):,}" if val != 0 else "0"
                
                # 列幅を文字数に合わせてフィット
                col_widths = {c: st.column_config.Column(width=f"{max(80, len(str(c))*16)}px") for c in result_with_analysis_str.columns}
                st.dataframe(result_with_analysis_str, use_container_width=True, hide_index=False, column_config=col_widths)

                # --- ここから複合表の作成 ---
                # 目標値
                # Cのみインプット値、それ以外はtarget_composition
                target_row = {}
                for e in mat_elements:
                    if e == "C" and user_c_input is not None:
                        v = user_c_input
                    else:
                        v = target_composition[e]
                    target_row[e] = v
                
                # 出湯前目標値（成分目標値から添加剤で増加する成分を引いた値）
                pre_tapping_target_row = {}
                for e in mat_elements:
                    if e == "C":
                        if mode == "FCD":
                            base_value = target_composition[e] + 0.08
                        else:
                            base_value = target_composition[e] + 0.07
                        v = base_value - additive_composition_pct[e]
                    else:
                        v = target_composition[e] - additive_composition_pct[e]
                    pre_tapping_target_row[e] = max(0.0, v)
                # 出湯後添加成分（旧:添加材由来）
                after_tapping_additive_row = {e: additive_composition_pct[e] for e in mat_elements}
                # 至急分析目標値（旧:残り目標成分）
                urgent_analysis_target_row = {e: urgent_analysis_target[e] for e in mat_elements}
                # 配合計算成分（旧:実際の成分達成度）
                achieved = np.dot(A_full, add_weights_masked)
                achieved_pct = achieved / total_weight_g * 100
                blend_calc_row = {e: v for e, v in zip(mat_elements, achieved_pct)}
                # 判定基準
                judge = {}
                for e in mat_elements:
                    if e == "Fe" or e not in selected_elements:
                        judge[e] = "-"
                        continue
                    # 判定用はfloatで取得
                    target = float(urgent_analysis_target.get(e, 0.0))
                    if target == 0.0:
                        judge[e] = "-"
                        continue
                    achieved_val = float(achieved_pct[mat_elements.index(e)])
                    tol = tolerance_values.get(e, 0.01)
                    tol_type = tolerance_types.get(e, "±")
                    
                    if tol_type == "±":
                        if abs(achieved_val - target) <= tol:
                            judge[e] = "○"
                        else:
                            judge[e] = f"× (許容範囲：±{tol})"
                    else:  # 以下
                        if achieved_val <= target + tol:
                            judge[e] = "○"
                        else:
                            judge[e] = f"× (許容値：{target + tol}以下)"
                # 判定行
                judge_row = {e: judge[e] for e in mat_elements}
                # 第1の表：成分目標値・出湯前目標値・出湯後添加成分
                table1_df = pd.DataFrame([
                    target_row,
                    pre_tapping_target_row,
                    after_tapping_additive_row
                ], index=[
                    "成分目標値(%)",
                    "出湯前目標値(%)",
                    "出湯後添加成分(%)"
                ])
                
                # 第2の表：至急分析目標値・配合計算成分・判定
                table2_df = pd.DataFrame([
                    urgent_analysis_target_row,
                    blend_calc_row,
                    judge_row
                ], index=[
                    "至急分析目標値(%)",
                    "配合計算成分(%)",
                    "判定"
                ])
                # 第1の表の表示用文字列化
                table1_disp = table1_df.astype(str)
                for row in ["成分目標値(%)", "出湯前目標値(%)", "出湯後添加成分(%)"]:
                    for e in mat_elements:
                        val = table1_df.at[row, e]
                        if isinstance(val, str):
                            table1_disp.at[row, e] = val
                        elif val == 0 or (isinstance(val, float) and abs(val) < 1e-12):
                            table1_disp.at[row, e] = "0"
                        else:
                            table1_disp.at[row, e] = f"{val:.3g}"
                
                # 第2の表の表示用文字列化
                table2_disp = table2_df.astype(str)
                for row in ["至急分析目標値(%)", "配合計算成分(%)"]:
                    for e in mat_elements:
                        val = table2_df.at[row, e]
                        if isinstance(val, str):
                            table2_disp.at[row, e] = val
                        elif val == 0 or (isinstance(val, float) and abs(val) < 1e-12):
                            table2_disp.at[row, e] = "0"
                        else:
                            table2_disp.at[row, e] = f"{val:.3g}"
                
                # 成分の値がすべて0の列を非表示（両方の表で共通）
                cols_to_show = []
                for e in mat_elements:
                    # 第1の表で0以外の値があるかチェック
                    table1_has_value = any(table1_disp.at[row, e] != "0" for row in ["成分目標値(%)", "出湯前目標値(%)", "出湯後添加成分(%)"])
                    # 第2の表で0以外の値があるかチェック
                    table2_has_value = any(table2_disp.at[row, e] != "0" for row in ["至急分析目標値(%)", "配合計算成分(%)"])
                    if table1_has_value or table2_has_value:
                        cols_to_show.append(e)
                
                table1_filtered = table1_disp[cols_to_show]
                table2_filtered = table2_disp[cols_to_show]
                # 選択元素の背景色を付ける関数
                def highlight_selected_elements_table(row):
                    sel_color = "background-color: #ffe599"  # 薄い黄色
                    result = []
                    for col in row.index:
                        if col in selected_elements:
                            result.append(sel_color)
                        else:
                            result.append("")
                    return result
                
                # 判定表用のハイライト関数
                def highlight_selected_and_ng(row):
                    ng_color = "background-color: #f4cccc"  # 薄い赤
                    sel_color = "background-color: #ffe599"  # 薄い黄色
                    result = []
                    if row.name == "判定":
                        for col, val in zip(row.index, row.values):
                            if isinstance(val, str) and val.startswith("×") and col in selected_elements:
                                result.append(ng_color)
                            elif col in selected_elements:
                                result.append(sel_color)
                            else:
                                result.append("")
                    else:
                        for col in row.index:
                            if col in selected_elements:
                                result.append(sel_color)
                            else:
                                result.append("")
                    return result
                
                # 第1の表表示
                st.markdown("**成分目標値・出湯前目標値・出湯後添加成分**")
                st.dataframe(
                    table1_filtered.astype(str).style.apply(
                        highlight_selected_elements_table, axis=1
                    ),
                    use_container_width=True,
                    key=f"table1_{current_tab_index}_{'_'.join(selected_elements)}"
                )
                
                # 第2の表表示
                st.markdown("**至急分析目標値・配合計算成分・判定**")
                st.dataframe(
                    table2_filtered.astype(str).style.apply(
                        highlight_selected_and_ng, axis=1
                    ),
                    use_container_width=True,
                    key=f"table2_{current_tab_index}_{'_'.join(selected_elements)}"
                )
                # 最大誤差も表示（至急分析目標値と比較）
                target_achieved = np.array([urgent_analysis_target[e] / 100 * total_weight_g for e in mat_elements])
                max_err = np.max(np.abs(achieved - target_achieved))
                st.markdown(f"**最大誤差（g）: {max_err:.3g}**")
                
                # 計算結果をセッションステートに保存（指示票で使用）
                calc_results = {}
                for i, mat in enumerate(material_names):
                    if add_weights is not None and i < len(add_weights):
                        calc_results[mat] = add_weights[i]
                st.session_state[f"calc_results_{current_tab_index}"] = calc_results
                
        # 変数の初期化（CSVダウンロード用）
        if 'additives_df_disp' not in locals():
            additives_df_disp = None
        
        # CSVダウンロード
        st.markdown("---")
        # 設定情報と表を統合してCSV出力
        csv_parts = []
        
        # 0. 設定情報
        csv_parts.append("設定情報")
        csv_parts.append(f"溶湯種別,{mode}")
        csv_parts.append(f"出湯温度（℃）,{tapping_temp}")
        csv_parts.append(f"溶解重量（kg）,{total_weight_kg}")
        if 'remaining_weight_kg' in locals():
            csv_parts.append(f"残湯量（kg）,{remaining_weight_kg}")
        else:
            csv_parts.append(f"残湯量（kg）,0.0")
        csv_parts.append("")
        
        # 1. 材料・添加材ごとの必要添加量による成分増加量（%）
        if 'inc_table' in locals():
            csv_parts.append("材料・添加材ごとの必要添加量による成分増加量（%）")
            csv_parts.append(inc_table.to_csv(index=True))
            csv_parts.append("")
        
        # 2. 添加材ごとの必要添加量（g）
        if 'additives_df_disp' in locals() and additives_df_disp is not None:
            csv_parts.append("添加材ごとの必要添加量（g）")
            csv_parts.append(additives_df_disp.to_csv(index=True))
            csv_parts.append("")
        
        # 3. 材料ごとの必要添加量（g）
        if 'result_with_analysis' in locals():
            csv_parts.append("材料ごとの必要添加量（g）")
            csv_parts.append(result_with_analysis.to_csv(index=True))
            csv_parts.append("")
        
        # 4. 成分目標値・出湯前目標値・出湯後添加成分
        if 'table1_filtered' in locals():
            csv_parts.append("成分目標値・出湯前目標値・出湯後添加成分")
            csv_parts.append(table1_filtered.to_csv(index=True))
            csv_parts.append("")
        
        # 5. 至急分析目標値・配合計算成分・判定
        if 'table2_filtered' in locals():
            csv_parts.append("至急分析目標値・配合計算成分・判定")
            csv_parts.append(table2_filtered.to_csv(index=True))
        
        # BOM付きUTF-8で出力
        csv_string = "\n".join(csv_parts)
        csv_data = '\ufeff' + csv_string
        
        # タブ番号を直接計算（ループのインデックスを保存）
        tab_index = current_tab_index  # ループのインデックスを保存
        current_tab_name = f"配合{tab_index + 1}"
        # ユニークなキーを生成
        import hashlib
        key_source = f"{test_name}_{current_tab_name}_{len(selected_elements)}"
        if 'selected_materials' in locals():
            key_source += f"_{len(selected_materials)}"
        dl_key = f"csv_download_{hashlib.md5(key_source.encode()).hexdigest()[:8]}"
        # 試験名をファイル名に含める
        safe_test_name = test_name.replace("/", "_").replace("\\", "_").replace(":", "_")
        tab_number = current_tab_name.replace('配合', '')
        file_name = f"{safe_test_name}_{current_tab_name}_結果.csv"
        st.download_button(
            label=f"📁 {file_name}をダウンロード",
            data=csv_data,
            file_name=file_name,
            mime="text/csv",
            key=dl_key
        )