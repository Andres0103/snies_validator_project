
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  ValidationResponse,
  ValidationErrorsResponse,
  ValidationHistoryResponse
} from '../models/validation.model';

@Injectable({
  providedIn: 'root'
})
export class ValidationApiService {

  private http = inject(HttpClient);

  private readonly apiUrl =
    'http://127.0.0.1:8000/api/validaciones';


  // Enviar archivos Excel
  uploadFiles(files: File[]): Observable<ValidationResponse> {

    const formData = new FormData();

    files.forEach(file => {
      formData.append('archivos', file, file.name);
    });

    return this.http.post<ValidationResponse>(
      this.apiUrl,
      formData
    );
  }


  // Consultar estado de una validación
  getValidation(id: string): Observable<ValidationResponse> {

    return this.http.get<ValidationResponse>(
      `${this.apiUrl}/${id}`
    );
  }


  // Consultar errores y advertencias
  getValidationErrors(
    id: string
  ): Observable<ValidationErrorsResponse> {

    return this.http.get<ValidationErrorsResponse>(
      `${this.apiUrl}/${id}/errores`
    );
  }


  // Consultar historial
  getHistory(): Observable<ValidationHistoryResponse> {

    return this.http.get<ValidationHistoryResponse>(
      this.apiUrl
    );
  }


  // Descargar reporte consolidado
  downloadReport(id: string): Observable<Blob> {

    return this.http.get(
      `${this.apiUrl}/${id}/reporte`,
      { responseType: 'blob' }
    );
  }


  // Descargar Excel marcado
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
