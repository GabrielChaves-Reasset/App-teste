import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
import fal_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIAnalyzer:
    """Handles AI-powered creditor extraction and analysis using Fal.ai API."""
    
    def __init__(self, model_id: str = "openai/gpt-4o"):
        self.model_id = model_id
        self.fal_key = os.getenv("FAL_KEY")
        self.logger = logger
    
    def extract_creditors(self, pdf_text: str, document_name: str) -> tuple[List[Dict[str, Any]], int]:
        """
        Extract creditor information from PDF text using AI.
        
        Args:
            pdf_text: Raw text from PDF
            document_name: Name/description of the document
            
        Returns:
            tuple: (List of creditor information dictionaries, count of creditors)
        """
        try:
            prompt = self._build_extraction_prompt(pdf_text, document_name)
            
            # Make API call to Fal.ai
            response = fal_client.run(
                "fal-ai/any-llm",
                arguments={
                    "model": self.model_id,
                    "prompt": prompt,
                    "temperature": 0.1,  # Low temperature for consistent extraction
                    "max_tokens": 4000
                }
            )
            
            # Extract and parse AI response
            ai_response = response.get('choices', [{}])[0].get('message', {}).get('content', '')

            if not ai_response:
                raise ValueError(f"A resposta da IA estava vazia. Resposta completa do fal_client: {response}")
            
            self.logger.info(f"AI Response length: {len(ai_response)} characters")
            self.logger.debug(f"Raw AI Response: {ai_response[:500]}...")
            
            # Parse JSON response with multiple strategies
            creditors = self._parse_ai_response(ai_response)
            
            self.logger.info(f"Successfully extracted {len(creditors)} creditors from {document_name}")
            return creditors, len(creditors)
            
        except Exception as e:
            self.logger.error(f"AI extraction failed: {e}")
            raise Exception(f"Erro na análise com IA: {str(e)}")
    
    def extract_creditors_from_chunks(self, chunks: List[Dict], document_name: str, progress_callback=None) -> tuple[List[Dict[str, Any]], int]:
        """
        Extract creditor information from PDF chunks and consolidate results.
        
        Args:
            chunks: List of text chunks with metadata
            document_name: Name/description of the document
            progress_callback: Optional callback function for progress updates
            
        Returns:
            tuple: (Consolidated list of creditor information, pre-consolidation count)
        """
        all_creditors = []
        
        try:
            for i, chunk in enumerate(chunks):
                chunk_text = chunk['text']
                start_page = chunk['start_page']
                end_page = chunk['end_page']
                total_pages = chunk['total_pages']
                
                self.logger.info(f"Processing chunk {i+1}/{len(chunks)} (pages {start_page}-{end_page})")
                
                if progress_callback:
                    progress_callback(i, len(chunks), start_page, end_page)
                
                # Extract creditors from this chunk
                prompt = self._build_extraction_prompt(
                    chunk_text, 
                    f"{document_name} - Páginas {start_page} a {end_page} de {total_pages}"
                )
                
                response = fal_client.run(
                    "fal-ai/any-llm",
                    arguments={
                        "model": self.model_id,
                        "prompt": prompt,
                        "temperature": 0.1,
                        "max_tokens": 4000
                    }
                )
                
                ai_response = response.get('choices', [{}])[0].get('message', {}).get('content', '')
                chunk_creditors = self._parse_ai_response(ai_response)
                
                # Add page range metadata to each creditor
                for creditor in chunk_creditors:
                    creditor['_source_pages'] = f"{start_page}-{end_page}"
                
                all_creditors.extend(chunk_creditors)
                self.logger.info(f"Extracted {len(chunk_creditors)} creditors from chunk {i+1}")
            
            # Consolidate duplicates using AI
            pre_consolidation_count = len(all_creditors)
            if pre_consolidation_count > 0:
                consolidated = self._consolidate_creditors_with_ai(all_creditors, document_name)
                self.logger.info(f"Consolidated to {len(consolidated)} unique creditors from {pre_consolidation_count} total extractions")
                return consolidated, pre_consolidation_count
            
            return all_creditors, pre_consolidation_count
            
        except Exception as e:
            self.logger.error(f"Chunk extraction failed: {e}")
            raise Exception(f"Erro na extração em blocos: {str(e)}")
    
    def _consolidate_creditors_with_ai(self, creditors: List[Dict], document_name: str) -> List[Dict[str, Any]]:
        """
        Use AI to consolidate duplicate creditors from multiple chunks.
        Processes in batches to handle large lists without losing data.
        
        Args:
            creditors: List of all creditors from all chunks
            document_name: Name of the document
            
        Returns:
            List[Dict]: Consolidated list without duplicates
        """
        try:
            # If list is small enough, process directly
            if len(creditors) <= 150:
                return self._consolidate_batch(creditors, document_name)
            
            # For large lists, process in batches and merge
            batch_size = 100
            consolidated_result = []
            
            self.logger.info(f"Consolidating {len(creditors)} creditors in batches of {batch_size}")
            
            # Process batches
            for i in range(0, len(creditors), batch_size):
                batch = creditors[i:i + batch_size]
                self.logger.info(f"Processing batch {i//batch_size + 1} with {len(batch)} creditors")
                
                # Consolidate this batch
                batch_consolidated = self._consolidate_batch(batch, f"{document_name} - Lote {i//batch_size + 1}")
                
                # Merge with existing consolidated results
                if consolidated_result:
                    # Combine and re-consolidate to remove cross-batch duplicates
                    combined = consolidated_result + batch_consolidated
                    consolidated_result = self._consolidate_batch(combined, document_name)
                else:
                    consolidated_result = batch_consolidated
            
            self.logger.info(f"Final consolidation: {len(consolidated_result)} unique creditors from {len(creditors)} total")
            return consolidated_result
            
        except Exception as e:
            self.logger.error(f"Consolidation failed: {e}")
            # Remove metadata fields and return original list
            for creditor in creditors:
                creditor.pop('_source_pages', None)
            return creditors
    
    def _consolidate_batch(self, creditors: List[Dict], document_name: str) -> List[Dict[str, Any]]:
        """
        Consolidate a single batch of creditors using AI.
        
        Args:
            creditors: List of creditors to consolidate
            document_name: Name/description for context
            
        Returns:
            List[Dict]: Consolidated creditors
        """
        try:
            prompt = f"""
Você é um especialista em consolidação de dados financeiros. Analise a seguinte lista de credores que pode conter duplicatas.

DOCUMENTO: {document_name}
CREDORES ({len(creditors)} total):
{json.dumps(creditors, indent=2, ensure_ascii=False)}

INSTRUÇÕES:
1. Identifique e consolide credores duplicados (mesmo credor mencionado múltiplas vezes)
2. Para duplicatas, mantenha apenas UMA entrada com todas as informações consolidadas
3. Use matching inteligente (considere variações de nome, formatação, etc.)
4. Preserve TODOS os credores únicos - não omita nenhum
5. Remova o campo "_source_pages" do resultado final

FORMATO DE SAÍDA:
Retorne APENAS um JSON válido com array de credores únicos consolidados:

[
  {{
    "nome": "Nome do Credor",
    "documento": "CNPJ/CPF",
    "valor": "Valor",
    // ... outros campos relevantes
  }}
]

IMPORTANTE: 
- Responda APENAS com o JSON, sem texto adicional
- Inclua TODOS os credores únicos, mesmo que não haja duplicatas
"""
            
            response = fal_client.run(
                "fal-ai/any-llm",
                arguments={
                    "model": self.model_id,
                    "prompt": prompt,
                    "temperature": 0.1,
                    "max_tokens": 8000
                }
            )
            
            ai_response = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            consolidated = self._parse_ai_response(ai_response)
            
            # Validate that we didn't lose creditors
            if consolidated and len(consolidated) > 0:
                return consolidated
            else:
                self.logger.warning("Batch consolidation returned empty, using original batch")
                for creditor in creditors:
                    creditor.pop('_source_pages', None)
                return creditors
            
        except Exception as e:
            self.logger.warning(f"Batch consolidation failed: {e}")
            for creditor in creditors:
                creditor.pop('_source_pages', None)
            return creditors
    
    def compare_creditors_with_ai(self, old_creditors: List[Dict], new_creditors: List[Dict]) -> Dict[str, Any]:
        """
        Use AI to intelligently compare creditor lists and identify changes.
        
        Args:
            old_creditors: List of creditors from old document
            new_creditors: List of creditors from new document
            
        Returns:
            Dict: Comparison results with categorized changes
        """
        try:
            prompt = self._build_comparison_prompt(old_creditors, new_creditors)
            
            # Make API call for comparison
            response = fal_client.run(
                "fal-ai/any-llm",
                arguments={
                    "model": self.model_id,
                    "prompt": prompt,
                    "temperature": 0.1,
                    "max_tokens": 6000
                }
            )
            
            ai_response = response.get('choices', [{}])[0].get('message', {}).get('content', '')

            if not ai_response:
                raise ValueError(f"A resposta da IA (comparação) estava vazia. Resposta completa do fal_client: {response}")
            
            self.logger.info(f"AI Comparison Response length: {len(ai_response)} characters")
            self.logger.debug(f"Raw AI Comparison Response: {ai_response[:500]}...")
            
            # Parse comparison results
            comparison_results = self._parse_comparison_response(ai_response)
            
            return comparison_results
            
        except Exception as e:
            self.logger.error(f"AI comparison failed: {e}")
            raise Exception(f"Erro na comparação com IA: {str(e)}")
    
    def _build_extraction_prompt(self, pdf_text: str, document_name: str) -> str:
        """Build prompt for creditor extraction."""
        return f"""
Você é um especialista em análise de documentos financeiros brasileiros. Analise o seguinte texto extraído de um Quadro Geral de Credores (QGC) e extraia TODAS as informações dos credores de forma estruturada.

DOCUMENTO: {document_name}

TEXTO DO PDF:
{pdf_text[:8000]}  # Limit text to avoid token limits

INSTRUÇÕES:
1. Identifique e extraia informações de TODOS os credores mencionados no documento
2. Para cada credor, extraia o máximo de informações disponíveis
3. Campos típicos incluem: nome, CNPJ/CPF, valor, categoria, classificação, garantia, etc.
4. Se um campo não estiver disponível, use null
5. Mantenha valores monetários como strings para preservar formatação original
6. Seja preciso e não invente informações

FORMATO DE SAÍDA:
Retorne APENAS um JSON válido com um array de objetos, onde cada objeto representa um credor:

[
  {{
    "nome": "Nome do Credor",
    "documento": "CNPJ/CPF se disponível",
    "valor": "Valor como string",
    "categoria": "Categoria se disponível",
    "classificacao": "Classificação se disponível",
    "garantia": "Tipo de garantia se disponível",
    "observacoes": "Observações adicionais se disponíveis"
  }}
]

IMPORTANTE: Responda APENAS com o JSON, sem texto adicional antes ou depois.
"""
    
    def _build_comparison_prompt(self, old_creditors: List[Dict], new_creditors: List[Dict]) -> str:
        """Build prompt for intelligent creditor comparison."""
        return f"""
Você é um especialista em análise comparativa de documentos financeiros. Compare duas listas de credores de diferentes versões de um Quadro Geral de Credores (QGC) e identifique mudanças de forma inteligente.

CREDORES DA VERSÃO ANTERIOR:
{json.dumps(old_creditors, indent=2, ensure_ascii=False)[:4000]}

CREDORES DA VERSÃO ATUAL:
{json.dumps(new_creditors, indent=2, ensure_ascii=False)[:4000]}

INSTRUÇÕES:
1. Compare os credores usando matching inteligente (considere variações no nome, formatação, etc.)
2. Identifique credores novos, removidos, modificados e inalterados
3. Para credores modificados, identifique especificamente quais campos mudaram
4. Calcule scores de confiança para os matches (0.0 a 1.0)
5. Seja preciso na identificação de mudanças

FORMATO DE SAÍDA:
Retorne APENAS um JSON válido com a seguinte estrutura:

{{
  "new_creditors": [
    // Credores que aparecem apenas na versão atual
  ],
  "removed_creditors": [
    // Credores que aparecem apenas na versão anterior
  ],
  "modified_creditors": [
    {{
      "creditor": // objeto do credor atual,
      "old_values": // campos que mudaram com valores antigos,
      "changes": // descrição das mudanças,
      "confidence_score": // score de 0.0 a 1.0
    }}
  ],
  "unchanged_creditors": [
    // Credores sem mudanças significativas
  ],
  "summary": {{
    "total_old": // número total de credores antigos,
    "total_new": // número total de credores novos,
    "new_count": // número de novos credores,
    "removed_count": // número de credores removidos,
    "modified_count": // número de credores modificados,
    "unchanged_count": // número de credores inalterados
  }}
}}

IMPORTANTE: Responda APENAS com o JSON, sem texto adicional.
"""
    
    def _parse_ai_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse AI response with multiple fallback strategies."""
        
        # Strategy 1: Direct JSON parsing
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Find JSON array pattern
        json_pattern = re.search(r'\[.*\]', response, re.DOTALL)
        if json_pattern:
            try:
                return json.loads(json_pattern.group(0))
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Clean and retry
        cleaned = response.strip()
        if cleaned.startswith('```') and cleaned.endswith('```'):
            cleaned = cleaned[3:-3].strip()
            if cleaned.startswith('json'):
                cleaned = cleaned[4:].strip()
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # If all strategies fail, return empty list with warning
        self.logger.warning(f"Failed to parse AI response: {response[:200]}...")
        return []
    
    def _parse_comparison_response(self, response: str) -> Dict[str, Any]:
        """Parse AI comparison response."""
        
        # Use similar parsing strategies as extraction
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Extract from code blocks
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Find JSON object pattern
        json_pattern = re.search(r'\{.*\}', response, re.DOTALL)
        if json_pattern:
            try:
                return json.loads(json_pattern.group(0))
            except json.JSONDecodeError:
                pass
        
        # Default empty result
        self.logger.warning(f"Failed to parse comparison response: {response[:200]}...")
        return {
            "new_creditors": [],
            "removed_creditors": [],
            "modified_creditors": [],
            "unchanged_creditors": [],
            "summary": {
                "total_old": 0,
                "total_new": 0,
                "new_count": 0,
                "removed_count": 0,
                "modified_count": 0,
                "unchanged_count": 0
            }
        }
