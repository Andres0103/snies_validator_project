
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  ValidationResponse,
  ValidationErrorsResponse,
  ValidationHistoryResponse
} from '../models/validation.model';

export type TemplateName =
  | 'CONSULTORIA'
  | 'EVENTO_CULTURAL'
  | 'ACTIVIDAD_CULTURAL'
  | 'SERVICIOS_EXTENSION'
  | 'PROYECTOS_EXTENSION'
  | 'CURSOS';

@Injectable({
  providedIn: 'root'
})
export class ValidationApiService {

  private http = inject(HttpClient);

  private readonly apiUrl =
    'http://127.0.0.1:8000/api/validaciones';

  /**
   * Envía los archivos Excel y la plantilla seleccionada.
   */
  uploadFiles(
    templateName: TemplateName,
    files: File[]
  ): Observable<ValidationResponse> {

    const formData = new FormData();

    formData.append('plantilla', templateName);

    files.forEach(file => {
      formData.append('archivos', file, file.name);
    });

    return this.http.post<ValidationResponse>(
      this.apiUrl,
      formData
    );
  }

  /**
   * Consulta el estado de una validación.
   */
  getValidation(id: string): Observable<ValidationResponse> {

    return this.http.get<ValidationResponse>(
      `${this.apiUrl}/${id}`
    );
  }

  /**
   * Consulta los errores y advertencias.
   */
  getValidationErrors(
    id: string
  ): Observable<ValidationErrorsResponse> {

    return this.http.get<ValidationErrorsResponse>(
      `${this.apiUrl}/${id}/errores`
    );
  }

  /**
   * Consulta el historial de validaciones.
   */
  getHistory(): Observable<ValidationHistoryResponse> {

    return this.http.get<ValidationHistoryResponse>(
      this.apiUrl
    );
  }

  /**
   * Descarga el reporte consolidado.
   */
  downloadReport(id: string): Observable<Blob> {

    return this.http.get(
      `${this.apiUrl}/${id}/reporte`,
      { responseType: 'blob' }
    );
  }

  /**
   * Descarga el archivo Excel marcado.
   */
  downloadMarkedFile(
    id: string,
    filename: string
  ): Observable<Blob> {

    return this.http.get(
      `${this.apiUrl}/${id}/archivos/${encodeURIComponent(filename)}`,
      { responseType: 'blob' }
    );
  }

}
