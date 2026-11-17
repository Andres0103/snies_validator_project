
import {
  ValidationResponse,
  ValidationIssue
} from './validation.model';

/**
 * Representa un archivo almacenado localmente.
 *
 * El contenido se guarda como Blob para poder recuperarlo
 * y descargarlo posteriormente.
 */
export interface StoredValidationFile {
  name: string;
  type: string;
  blob: Blob;
}

/**
 * Registro completo de una validación almacenada en IndexedDB.
 *
 * Extiende ValidationResponse para conservar la estructura
 * que ya utiliza la pantalla de resultados.
 */
export interface LocalValidationRecord extends ValidationResponse {
  savedAt: string;

  // Archivos Excel que el usuario cargó originalmente.
  originalFiles: StoredValidationFile[];

  // Archivos Excel marcados que generó el backend.
  generatedFiles: StoredValidationFile[];

  // Reporte consolidado generado por el backend.
  report: StoredValidationFile | null;

  // Errores y advertencias de la validación.
  issues: ValidationIssue[];

  /**
   * Indica si la consulta de incidencias terminó correctamente.
   *
   * true: la consulta fue exitosa, incluso si no encontró incidencias.
   * false: la consulta falló y no podemos asegurar que no existan incidencias.
   */
  issuesLoadedSuccessfully: boolean;
}
