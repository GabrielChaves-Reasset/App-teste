import os
import streamlit as st
import pandas as pd
from utils.pdf_processor import PDFProcessor
from utils.ai_analyzer import AIAnalyzer
from utils.comparison_engine import ComparisonEngine
from utils.data_exporter import DataExporter

# Page configuration
st.set_page_config(
    page_title="QGC Comparador - PDF Creditor Analysis",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'comparison_results' not in st.session_state:
    st.session_state.comparison_results = None
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False

def main():
    st.title("📊 QGC Comparador")
    st.markdown("**Ferramenta para comparação inteligente de Quadros Gerais de Credores usando IA**")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Model selection
        st.subheader("Modelo de IA")
        model_options = {
            "ChatGPT-4": "openai/gpt-4o",
            "GPT-5": "openai/gpt-5-chat",
            "Gemini-2.5-Pro": "google/gemini-2.5-pro"
        }
        
        selected_model_label = st.selectbox(
            "Escolha o modelo de linguagem:",
            list(model_options.keys()),
            help="Modelos premium são cobrados a 10x a taxa padrão"
        )
        selected_model = model_options[selected_model_label]
        
        # Match threshold
        match_threshold = st.slider(
            "Limiar de correspondência:",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.05,
            help="Quão similar dois credores devem ser para serem considerados o mesmo"
        )
        
        # API status
        fal_key = os.getenv("FAL_KEY")
        if fal_key:
            st.success("✅ API Key configurada")
        else:
            st.error("❌ FAL_KEY não encontrada nas variáveis de ambiente")
    
    # Main content area
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📄 QGC Anterior")
        old_file = st.file_uploader(
            "Carregue o QGC anterior:",
            type=['pdf'],
            key="old_file",
            help="Versão antiga do Quadro Geral de Credores"
        )
        if old_file:
            st.success(f"✅ {old_file.name}")
    
    with col2:
        st.subheader("📄 QGC Atual")
        new_file = st.file_uploader(
            "Carregue o QGC atual:",
            type=['pdf'],
            key="new_file",
            help="Versão atual do Quadro Geral de Credores"
        )
        if new_file:
            st.success(f"✅ {new_file.name}")
    
    # Process files when both are uploaded
    if old_file and new_file and st.button("🔍 Iniciar Comparação", type="primary"):
        if not fal_key:
            st.error("❌ Por favor, configure a variável de ambiente FAL_KEY")
            return
        
        with st.spinner("Processando PDFs e executando análise com IA..."):
            try:
                # Initialize processors
                pdf_processor = PDFProcessor()
                ai_analyzer = AIAnalyzer(selected_model)
                comparison_engine = ComparisonEngine(match_threshold)
                
                # Process PDFs
                st.info("📖 Extraindo texto dos PDFs...")
                old_text = pdf_processor.extract_text(old_file)
                new_text = pdf_processor.extract_text(new_file)
                
                # Analyze with AI
                st.info(f"🤖 Analisando com {selected_model_label}...")
                old_creditors = ai_analyzer.extract_creditors(old_text, "QGC Anterior")
                new_creditors = ai_analyzer.extract_creditors(new_text, "QGC Atual")
                
                # Compare results
                st.info("⚖️ Comparando resultados...")
                comparison_results = comparison_engine.compare_creditors(old_creditors, new_creditors)
                
                st.session_state.comparison_results = comparison_results
                st.session_state.processing_complete = True
                
                st.success("✅ Análise concluída!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erro durante o processamento: {str(e)}")
    
    # Display results
    if st.session_state.processing_complete and st.session_state.comparison_results:
        display_results(st.session_state.comparison_results)

def display_results(results):
    st.header("📋 Resultados da Comparação")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Novos Credores", len(results['new_creditors']))
    with col2:
        st.metric("Credores Removidos", len(results['removed_creditors']))
    with col3:
        st.metric("Credores Modificados", len(results['modified_creditors']))
    with col4:
        st.metric("Credores Inalterados", len(results['unchanged_creditors']))
    
    # Detailed results in tabs
    tab1, tab2, tab3, tab4 = st.tabs(["✅ Novos", "❌ Removidos", "📝 Modificados", "📊 Todos os Dados"])
    
    with tab1:
        st.subheader("Novos Credores")
        if results['new_creditors']:
            df_new = pd.DataFrame(results['new_creditors'])
            st.dataframe(df_new, use_container_width=True)
        else:
            st.info("Nenhum novo credor identificado.")
    
    with tab2:
        st.subheader("Credores Removidos")
        if results['removed_creditors']:
            df_removed = pd.DataFrame(results['removed_creditors'])
            st.dataframe(df_removed, use_container_width=True)
        else:
            st.info("Nenhum credor foi removido.")
    
    with tab3:
        st.subheader("Credores Modificados")
        if results['modified_creditors']:
            df_modified = pd.DataFrame(results['modified_creditors'])
            st.dataframe(df_modified, use_container_width=True)
        else:
            st.info("Nenhuma modificação identificada.")
    
    with tab4:
        st.subheader("Resumo Completo")
        summary_data = []
        
        for creditor in results['new_creditors']:
            creditor['Status'] = 'Novo'
            summary_data.append(creditor)
        
        for creditor in results['removed_creditors']:
            creditor['Status'] = 'Removido'
            summary_data.append(creditor)
        
        for creditor in results['modified_creditors']:
            creditor['Status'] = 'Modificado'
            summary_data.append(creditor)
        
        for creditor in results['unchanged_creditors']:
            creditor['Status'] = 'Inalterado'
            summary_data.append(creditor)
        
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            st.dataframe(df_summary, use_container_width=True)
    
    # Export options
    st.header("💾 Exportar Resultados")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 Baixar como CSV"):
            try:
                exporter = DataExporter()
                csv_data = exporter.export_to_csv(results)
                st.download_button(
                    label="💾 Download CSV",
                    data=csv_data,
                    file_name="qgc_comparison_results.csv",
                    mime="text/csv"
                )
            except Exception as e:
                st.error(f"Erro ao gerar CSV: {str(e)}")
    
    with col2:
        if st.button("📈 Baixar como Excel"):
            try:
                exporter = DataExporter()
                excel_data = exporter.export_to_excel(results)
                st.download_button(
                    label="💾 Download Excel",
                    data=excel_data,
                    file_name="qgc_comparison_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Erro ao gerar Excel: {str(e)}")

if __name__ == "__main__":
    main()
