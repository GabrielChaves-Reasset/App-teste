import io
import pandas as pd
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataExporter:
    """Handles data export functionality for comparison results."""
    
    def __init__(self):
        self.logger = logger
    
    def export_to_csv(self, results: Dict[str, Any]) -> bytes:
        """
        Export comparison results to CSV format.
        
        Args:
            results: Comparison results dictionary
            
        Returns:
            bytes: CSV data as bytes
        """
        try:
            # Combine all results into a single dataset
            combined_data = []
            
            # Add new creditors
            for creditor in results.get('new_creditors', []):
                creditor_data = creditor.copy()
                creditor_data['Status'] = 'NOVO'
                creditor_data['Mudanças'] = 'Credor adicionado na nova versão'
                combined_data.append(creditor_data)
            
            # Add removed creditors
            for creditor in results.get('removed_creditors', []):
                creditor_data = creditor.copy()
                creditor_data['Status'] = 'REMOVIDO'
                creditor_data['Mudanças'] = 'Credor removido da nova versão'
                combined_data.append(creditor_data)
            
            # Add modified creditors
            for item in results.get('modified_creditors', []):
                creditor_data = item.get('creditor', {}).copy()
                creditor_data['Status'] = 'MODIFICADO'
                creditor_data['Mudanças'] = item.get('changes', 'Modificações identificadas')
                creditor_data['Score_Confiança'] = item.get('confidence_score', 1.0)
                
                # Add old values for comparison
                old_values = item.get('old_values', {})
                for key, old_value in old_values.items():
                    creditor_data[f'Valor_Anterior_{key}'] = old_value
                
                combined_data.append(creditor_data)
            
            # Add unchanged creditors
            for creditor in results.get('unchanged_creditors', []):
                creditor_data = creditor.copy()
                creditor_data['Status'] = 'INALTERADO'
                creditor_data['Mudanças'] = 'Nenhuma mudança identificada'
                combined_data.append(creditor_data)
            
            if not combined_data:
                # Create empty dataframe with basic structure
                df = pd.DataFrame(columns=['Status', 'Mudanças'])
            else:
                df = pd.DataFrame(combined_data)
            
            # Convert to CSV
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False, encoding='utf-8')
            csv_data = csv_buffer.getvalue().encode('utf-8')
            
            self.logger.info(f"CSV export successful: {len(df)} records")
            return csv_data
            
        except Exception as e:
            self.logger.error(f"CSV export failed: {e}")
            raise Exception(f"Erro ao exportar CSV: {str(e)}")
    
    def export_to_excel(self, results: Dict[str, Any]) -> bytes:
        """
        Export comparison results to Excel format with multiple sheets.
        
        Args:
            results: Comparison results dictionary
            
        Returns:
            bytes: Excel data as bytes
        """
        try:
            excel_buffer = io.BytesIO()
            
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                
                # Summary sheet
                summary = results.get('summary', {})
                summary_df = pd.DataFrame([{
                    'Métrica': 'Total Credores Anterior',
                    'Valor': summary.get('total_old', 0)
                }, {
                    'Métrica': 'Total Credores Atual',
                    'Valor': summary.get('total_new', 0)
                }, {
                    'Métrica': 'Novos Credores',
                    'Valor': summary.get('new_count', 0)
                }, {
                    'Métrica': 'Credores Removidos',
                    'Valor': summary.get('removed_count', 0)
                }, {
                    'Métrica': 'Credores Modificados',
                    'Valor': summary.get('modified_count', 0)
                }, {
                    'Métrica': 'Credores Inalterados',
                    'Valor': summary.get('unchanged_count', 0)
                }])
                summary_df.to_excel(writer, sheet_name='Resumo', index=False)
                
                # New creditors sheet
                if results.get('new_creditors'):
                    new_df = pd.DataFrame(results['new_creditors'])
                    new_df.to_excel(writer, sheet_name='Novos Credores', index=False)
                
                # Removed creditors sheet
                if results.get('removed_creditors'):
                    removed_df = pd.DataFrame(results['removed_creditors'])
                    removed_df.to_excel(writer, sheet_name='Credores Removidos', index=False)
                
                # Modified creditors sheet
                if results.get('modified_creditors'):
                    modified_data = []
                    for item in results['modified_creditors']:
                        creditor_data = item.get('creditor', {}).copy()
                        creditor_data['Mudanças'] = item.get('changes', '')
                        creditor_data['Score_Confiança'] = item.get('confidence_score', 1.0)
                        
                        # Add old values
                        old_values = item.get('old_values', {})
                        for key, old_value in old_values.items():
                            creditor_data[f'Valor_Anterior_{key}'] = old_value
                        
                        modified_data.append(creditor_data)
                    
                    modified_df = pd.DataFrame(modified_data)
                    modified_df.to_excel(writer, sheet_name='Credores Modificados', index=False)
                
                # Unchanged creditors sheet
                if results.get('unchanged_creditors'):
                    unchanged_df = pd.DataFrame(results['unchanged_creditors'])
                    unchanged_df.to_excel(writer, sheet_name='Credores Inalterados', index=False)
                
                # Combined data sheet
                combined_data = []
                
                for creditor in results.get('new_creditors', []):
                    creditor_copy = creditor.copy()
                    creditor_copy['Status'] = 'NOVO'
                    combined_data.append(creditor_copy)
                
                for creditor in results.get('removed_creditors', []):
                    creditor_copy = creditor.copy()
                    creditor_copy['Status'] = 'REMOVIDO'
                    combined_data.append(creditor_copy)
                
                for item in results.get('modified_creditors', []):
                    creditor_copy = item.get('creditor', {}).copy()
                    creditor_copy['Status'] = 'MODIFICADO'
                    creditor_copy['Mudanças'] = item.get('changes', '')
                    combined_data.append(creditor_copy)
                
                for creditor in results.get('unchanged_creditors', []):
                    creditor_copy = creditor.copy()
                    creditor_copy['Status'] = 'INALTERADO'
                    combined_data.append(creditor_copy)
                
                if combined_data:
                    combined_df = pd.DataFrame(combined_data)
                    combined_df.to_excel(writer, sheet_name='Todos os Dados', index=False)
            
            excel_data = excel_buffer.getvalue()
            self.logger.info("Excel export successful")
            return excel_data
            
        except Exception as e:
            self.logger.error(f"Excel export failed: {e}")
            raise Exception(f"Erro ao exportar Excel: {str(e)}")
