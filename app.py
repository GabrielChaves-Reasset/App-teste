import os
import streamlit as st
import pandas as pd
from utils.pdf_processor import PDFProcessor
from utils.ai_analyzer import AIAnalyzer
from utils.data_exporter import DataExporter
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="QGC Analisador IA - Análise Inteligente de Documentos",
    page_icon="🤖",
    layout="wide"
)

# Function to load external CSS
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Load custom CSS
load_css("style.css")

# Initialize session state
if 'comparison_results' not in st.session_state:
    st.session_state.comparison_results = None
if 'single_analysis_results' not in st.session_state:
    st.session_state.single_analysis_results = None
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'ai_logs' not in st.session_state:
    st.session_state.ai_logs = []
if 'fal_key' not in st.session_state:
    st.session_state.fal_key = ""
if 'analysis_mode' not in st.session_state:
    st.session_state.analysis_mode = "Análise Comparativa"


def main():
    # Header
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title("🤖 QGC Analisador IA")
    st.markdown("**Análise inteligente de Quadros Gerais de Credores usando IA avançada**")
    st.markdown('</div>', unsafe_allow_html=True)

    # Sidebar configuration
    with st.sidebar:
        build_sidebar()

    # Main content area
    st.header("🎯 Modo de Análise")
    analysis_mode = st.radio(
        "Escolha o que você quer fazer:",
        ("Análise Comparativa", "Análise Única"),
        horizontal=True,
        label_visibility="collapsed",
        key="analysis_mode_selector"
    )

    # Reset state if mode changes
    if st.session_state.analysis_mode != analysis_mode:
        reset_state()
        st.session_state.analysis_mode = analysis_mode
        st.rerun()


    if analysis_mode == "Análise Comparativa":
        run_comparative_analysis()
    elif analysis_mode == "Análise Única":
        run_single_analysis()


def build_sidebar():
    """Builds the sidebar UI components."""
    st.header("⚙️ Configurações")

    # API Key Input
    st.subheader("🔑 Chave da API")
    st.session_state.fal_key = st.text_input(
        "Insira sua FAL_KEY:",
        type="password",
        value=st.session_state.get('fal_key', ''),
        help="A chave é necessária para as chamadas de IA. Ela não será armazenada."
    )

    # Check API key status
    env_fal_key = os.getenv("FAL_KEY")
    final_fal_key = st.session_state.fal_key or env_fal_key

    if final_fal_key:
        st.success("✅ Chave da API pronta")
        masked_key = final_fal_key[:8] + "..." + final_fal_key[-4:] if len(final_fal_key) > 10 else final_fal_key
        st.caption(f"Usando chave: {masked_key}")
    else:
        st.error("❌ Nenhuma chave da API configurada")
        st.markdown("""
        Para usar este aplicativo, insira sua chave no campo acima ou configure a variável de ambiente `FAL_KEY`.
        1. Acesse [fal.ai](https://fal.ai)
        2. Crie uma conta e gere uma API key.
        """)

    # Model selection
    st.subheader("🧠 Modelo de IA")
    model_options = {
        "🔥 GPT-4o (Recomendado)": "openai/gpt-4o",
        "🚀 GPT-4o Mini (Rápido)": "openai/gpt-4o-mini",
        "🎯 Claude-3.7 Sonnet (Novo)": "anthropic/claude-3.7-sonnet",
        "🧠 Claude-3.5 Sonnet": "anthropic/claude-3.5-sonnet",
        "💎 Gemini-2.5-Pro": "google/gemini-2.5-pro",
    }
    selected_model_label = st.selectbox(
        "Escolha o modelo de IA:",
        list(model_options.keys()),
        help="Diferentes modelos têm características únicas. GPT-4o é recomendado para melhor precisão."
    )
    st.session_state.selected_model = model_options[selected_model_label]
    st.session_state.selected_model_label = selected_model_label

    # Advanced settings
    with st.expander("🔧 Configurações Avançadas"):
        st.session_state.show_debug_logs = st.checkbox("Mostrar logs de debug da IA", value=False)
        st.session_state.use_chunking = st.checkbox(
            "Processar em blocos (PDFs grandes)",
            value=True,
            help="Divide o PDF em blocos para processamento mais eficiente."
        )
        if st.session_state.use_chunking:
            st.session_state.pages_per_chunk = st.slider(
                "Páginas por bloco:", min_value=5, max_value=50, value=20, step=5
            )
        else:
            st.session_state.pages_per_chunk = None
        st.session_state.ai_temperature = st.slider(
            "Temperatura da IA:", min_value=0.0, max_value=1.0, value=0.1, step=0.05,
            help="Menor = mais determinístico, Maior = mais criativo."
        )


def run_comparative_analysis():
    """UI and logic for comparative analysis."""
    st.header("📂 Upload de Documentos para Comparação")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📄 QGC Anterior")
        old_file = st.file_uploader("Arraste ou selecione o PDF:", type=['pdf'], key="old_file", help="Versão anterior do QGC.")
        if old_file:
            st.success(f"✅ Carregado: **{old_file.name}**")
    with col2:
        st.markdown("### 📄 QGC Atual")
        new_file = st.file_uploader("Arraste ou selecione o PDF:", type=['pdf'], key="new_file", help="Versão atual do QGC.")
        if new_file:
            st.success(f"✅ Carregado: **{new_file.name}**")

    if old_file and new_file:
        st.markdown("---")
        if st.button("🚀 Iniciar Análise Comparativa", type="primary", use_container_width=True):
            final_fal_key = st.session_state.fal_key or os.getenv("FAL_KEY")
            if not final_fal_key:
                st.error("❌ Configure a chave da API para continuar.")
                return
            os.environ['FAL_KEY'] = final_fal_key # Set for fal-client
            
            st.session_state.processing_mode = "comparative"
            process_documents(old_file, new_file)

    if st.session_state.processing_complete and st.session_state.comparison_results:
        display_comparison_results(st.session_state.comparison_results, st.session_state.show_debug_logs)


def run_single_analysis():
    """UI and logic for single file analysis."""
    st.header("📂 Upload de Documento para Análise")
    qgc_file = st.file_uploader("Arraste ou selecione o PDF:", type=['pdf'], key="single_file", help="QGC a ser analisado.")
    if qgc_file:
        st.success(f"✅ Carregado: **{qgc_file.name}**")

    if qgc_file:
        st.markdown("---")
        if st.button("🚀 Iniciar Análise Única", type="primary", use_container_width=True):
            final_fal_key = st.session_state.fal_key or os.getenv("FAL_KEY")
            if not final_fal_key:
                st.error("❌ Configure a chave da API para continuar.")
                return
            os.environ['FAL_KEY'] = final_fal_key # Set for fal-client

            st.session_state.processing_mode = "single"
            process_single_document(qgc_file)

    if st.session_state.processing_complete and st.session_state.single_analysis_results:
        display_single_results(st.session_state.single_analysis_results, st.session_state.show_debug_logs)


def process_documents(old_file, new_file):
    """Process comparative analysis."""
    reset_state(full=False)
    st.session_state.processing_complete = False
    progress_bar = st.progress(0, "Iniciando análise comparativa...")
    status_text = st.empty()
    
    try:
        pdf_processor = PDFProcessor()
        ai_analyzer = AIAnalyzer(st.session_state.selected_model)
        
        def extract(file, name, progress_start, progress_end):
            status_text.info(f"📖 Extraindo texto de: {name}")
            if st.session_state.use_chunking:
                chunks = pdf_processor.extract_text_in_chunks(file, st.session_state.pages_per_chunk)
                st.session_state.ai_logs.append({"step": f"Extração de Chunks ({name})", "chunks": len(chunks)})
                
                def progress_callback(idx, total, sp, ep):
                    progress = progress_start + int(((idx+1) / total) * (progress_end - progress_start))
                    progress_bar.progress(progress)
                    status_text.info(f"🤖 Analisando {name} - Bloco {idx+1}/{total} (pág. {sp}-{ep})")

                creditors, pre_consolidation_count = ai_analyzer.extract_creditors_from_chunks(chunks, name, progress_callback)
                st.session_state.ai_logs.append({
                    "step": f"Consolidação IA ({name})",
                    "creditors_before": pre_consolidation_count,
                    "creditors_after": len(creditors),
                    "reduction": pre_consolidation_count - len(creditors)
                })
                return creditors
            else:
                text = pdf_processor.extract_text(file)
                st.session_state.ai_logs.append({"step": f"Extração de Texto ({name})", "length": len(text)})
                progress_bar.progress(progress_start + 5)
                status_text.info(f"🤖 Analisando {name} com IA...")
                creditors, count = ai_analyzer.extract_creditors(text, name)
                st.session_state.ai_logs.append({
                    "step": f"Extração IA ({name})",
                    "creditors_found": count,
                    "processing_mode": "full"
                })
                progress_bar.progress(progress_end)
                return creditors

        old_creditors = extract(old_file, "QGC Anterior", 5, 45)
        new_creditors = extract(new_file, "QGC Atual", 45, 85)
        
        st.session_state.ai_logs.append({
            "step": "Extração de Credores Concluída",
            "old_creditors_count": len(old_creditors),
            "new_creditors_count": len(new_creditors),
        })

        status_text.info("⚖️ Comparando listas de credores com IA...")
        progress_bar.progress(90)
        comparison_results = ai_analyzer.compare_creditors_with_ai(old_creditors, new_creditors)
        
        st.session_state.comparison_results = comparison_results
        st.session_state.processing_complete = True
        
        progress_bar.progress(100)
        status_text.success("✅ Análise comparativa concluída!")
        time.sleep(1)
        st.rerun()

    except Exception as e:
        status_text.error(f"❌ Erro no processamento: {e}")
        st.exception(e)
        progress_bar.empty()


def process_single_document(qgc_file):
    """Process single analysis."""
    reset_state(full=False)
    st.session_state.processing_complete = False
    progress_bar = st.progress(0, "Iniciando análise do documento...")
    status_text = st.empty()

    try:
        pdf_processor = PDFProcessor()
        ai_analyzer = AIAnalyzer(st.session_state.selected_model)

        status_text.info("📖 Extraindo texto do PDF...")
        if st.session_state.use_chunking:
            chunks = pdf_processor.extract_text_in_chunks(qgc_file, st.session_state.pages_per_chunk)
            st.session_state.ai_logs.append({"step": "Extração de Chunks", "chunks": len(chunks)})
            
            def progress_callback(idx, total, sp, ep):
                progress = 10 + int(((idx+1) / total) * 80)
                progress_bar.progress(progress)
                status_text.info(f"🤖 Analisando Bloco {idx+1}/{total} (pág. {sp}-{ep})")

            creditors, pre_consolidation_count = ai_analyzer.extract_creditors_from_chunks(chunks, qgc_file.name, progress_callback)
            st.session_state.ai_logs.append({
                "step": "Consolidação IA",
                "creditors_before": pre_consolidation_count,
                "creditors_after": len(creditors),
                "reduction": pre_consolidation_count - len(creditors)
            })
        else:
            text = pdf_processor.extract_text(qgc_file)
            st.session_state.ai_logs.append({"step": "Extração de Texto", "length": len(text)})
            progress_bar.progress(20)
            status_text.info("🤖 Analisando documento com IA...")
            creditors, count = ai_analyzer.extract_creditors(text, qgc_file.name)
            st.session_state.ai_logs.append({
                "step": "Extração IA",
                "creditors_found": count,
                "processing_mode": "full"
            })
            progress_bar.progress(90)

        st.session_state.single_analysis_results = creditors
        st.session_state.processing_complete = True

        progress_bar.progress(100)
        status_text.success("✅ Análise do documento concluída!")
        time.sleep(1)
        st.rerun()

    except Exception as e:
        status_text.error(f"❌ Erro no processamento: {e}")
        st.exception(e)
        progress_bar.empty()


def display_comparison_results(results, show_logs=False):
    """Display comprehensive comparison analysis results."""
    st.header("📊 Resultados da Análise Comparativa")
    summary = results.get('summary', {})
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📈 Novos Credores", summary.get('new_count', 0))
    col2.metric("📉 Removidos", summary.get('removed_count', 0))
    col3.metric("✏️ Modificados", summary.get('modified_count', 0))
    col4.metric("✅ Inalterados", summary.get('unchanged_count', 0))

    tab_titles = ["🆕 Novos", "🗑️ Removidos", "📝 Modificados", "📋 Todos", "🔍 Debug IA" if show_logs else "ℹ️ Resumo"]
    tabs = st.tabs(tab_titles)

    with tabs[0]:
        st.subheader("Novos Credores Identificados")
        new_creditors = results.get('new_creditors', [])
        st.dataframe(pd.DataFrame(new_creditors), use_container_width=True)

    with tabs[1]:
        st.subheader("Credores Removidos")
        removed_creditors = results.get('removed_creditors', [])
        st.dataframe(pd.DataFrame(removed_creditors), use_container_width=True)

    with tabs[2]:
        st.subheader("Credores com Modificações")
        modified_creditors = results.get('modified_creditors', [])
        st.json(modified_creditors, expanded=False)

    with tabs[3]:
        st.subheader("Dados Consolidados")
        st.info("Visualização de dados consolidados em desenvolvimento.")

    with tabs[4]:
        if show_logs:
            st.subheader("🔍 Debug da Análise IA")
            st.json(st.session_state.ai_logs)
        else:
            st.subheader("ℹ️ Resumo da Análise")
            st.write(summary)

    st.markdown("---")
    if st.button("🔄 Nova Análise Comparativa", use_container_width=True):
        reset_state()
        st.rerun()


def display_single_results(results, show_logs=False):
    """Display single analysis results."""
    st.header("📊 Resultados da Análise do Documento")
    
    st.metric("👥 Total de Credores Identificados", len(results))

    tab_titles = ["📋 Lista de Credores", "🔍 Debug IA" if show_logs else "ℹ️ Informações"]
    tabs = st.tabs(tab_titles)

    with tabs[0]:
        st.dataframe(pd.DataFrame(results), use_container_width=True, height=600)

    with tabs[1]:
        if show_logs:
            st.subheader("🔍 Debug da Análise IA")
            st.json(st.session_state.ai_logs)
        else:
            st.subheader("ℹ️ Informações")
            st.info(f"A análise com IA identificou {len(results)} credores no documento fornecido.")

    st.markdown("---")
    if st.button("🔄 Nova Análise Única", use_container_width=True):
        reset_state()
        st.rerun()


def reset_state(full=True):
    """Resets the session state for a new analysis."""
    st.session_state.processing_complete = False
    st.session_state.ai_logs = []
    st.session_state.comparison_results = None
    st.session_state.single_analysis_results = None
    
    if full:
        st.session_state.analysis_mode = "Análise Comparativa"


if __name__ == "__main__":
    main()