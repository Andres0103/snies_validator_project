
import { Component, OnInit, inject } from '@angular/core';

import { ValidationApiService } from '../../core/services/validation-api.service';

import {
  ValidationResponse,
  ValidationIssue
} from '../../core/models/validation.model';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [],
  templateUrl: './history.html',
  styleUrl: './history.scss'
})
export class History implements OnInit {

  private validationApi = inject(ValidationApiService);

  validations: ValidationResponse[] = [];

  selectedValidation: ValidationResponse | null = null;

  issues: ValidationIssue[] = [];

  isLoading = false;

  isLoadingIssues = false;

  errorMessage = '';


  ngOnInit(): void {
    this.loadHistory();
  }


  // Consultar historial
  loadHistory(): void {

    this.isLoading = true;
    this.errorMessage = '';

    this.validationApi.getHistory().subscribe({

      next: response => {

        this.validations = response.items;

        this.isLoading = false;
      },

      error: error => {

        console.error('Error consultando historial:', error);

        this.errorMessage =
          'No fue posible consultar el historial.';

        this.isLoading = false;
      }

    });
  }


  // Consultar detalles de una validación
  viewDetails(validation: ValidationResponse): void {

    this.selectedValidation = validation;

    this.issues = [];

    this.isLoadingIssues = true;

    this.validationApi
      .getValidationErrors(validation.id)
      .subscribe({

        next: response => {

          this.issues = response.items;

          this.isLoadingIssues = false;
        },

        error: error => {

          console.error('Error consultando incidencias:', error);

          this.errorMessage =
            'No fue posible consultar los detalles.';

          this.isLoadingIssues = false;
        }

      });
  }


  closeDetails(): void {

    this.selectedValidation = null;
    this.issues = [];
  }


  // Descargar reporte
  downloadReport(validation: ValidationResponse): void {

    this.validationApi
      .downloadReport(validation.id)
      .subscribe({

        next: blob => {
          this.saveBlob(
            blob,
            `reporte_validacion_${validation.id}.xlsx`
          );
        },

        error: error => {
          console.error('Error descargando reporte:', error);
          this.errorMessage = 'No fue posible descargar el reporte.';
        }

      });
  }


  // Descargar Excel marcado
  downloadMarkedFile(
    validation: ValidationResponse,
    filename: string
  ): void {

    this.validationApi
      .downloadMarkedFile(validation.id, filename)
      .subscribe({

        next: blob => {
          this.saveBlob(blob, filename);
        },

        error: error => {
          console.error('Error descargando Excel marcado:', error);
          this.errorMessage = 'No fue posible descargar el archivo.';
        }

      });
  }


  private saveBlob(blob: Blob, filename: string): void {

    const url = window.URL.createObjectURL(blob);

    const link = document.createElement('a');

    link.href = url;
    link.download = filename;

    link.click();

    window.URL.revokeObjectURL(url);
  }


  formatDate(value: string): string {

    return new Date(value).toLocaleString('es-CO', {
      dateStyle: 'short',
      timeStyle: 'short'
    });
  }

}
