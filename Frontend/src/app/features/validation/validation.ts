import {
  Component,
  OnDestroy,
  ChangeDetectorRef,
  inject
} from '@angular/core';
import { Subscription, timer } from 'rxjs';
import { switchMap, takeWhile } from 'rxjs/operators';

import { ValidationApiService } from '../../core/services/validation-api.service';

import {
  ValidationResponse,
  ValidationIssue
} from '../../core/models/validation.model';

@Component({
  selector: 'app-validation',
  standalone: true,
  imports: [],
  templateUrl: './validation.html',
  styleUrl: './validation.scss'
})
export class Validation implements OnDestroy {

  private readonly validationApi = inject(ValidationApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  private pollingSubscription?: Subscription;

  selectedFiles: File[] = [];

  validationResult: ValidationResponse | null = null;

  issues: ValidationIssue[] = [];

  errorMessage = '';

  isUploading = false;

  isProcessing = false;

  isLoadingIssues = false;

  showSuccessMessage = false;



  // =====================================================
  // SELECCIÓN DE ARCHIVOS
  // =====================================================

  onFilesSelected(event: Event): void {

    const input = event.target as HTMLInputElement;

    if (!input.files) {
      return;
    }

    const files = Array.from(input.files);

    const validFiles = files.filter(file =>
      file.name.toLowerCase().endsWith('.xlsx')
    );

    this.showSuccessMessage = false;

    if (validFiles.length !== files.length) {
      this.errorMessage =
        'Solo se permiten archivos Excel con extensión .xlsx.';
    } else {
      this.errorMessage = '';
    }

    for (const file of validFiles) {

      const exists = this.selectedFiles.some(selected =>
        selected.name === file.name &&
        selected.size === file.size &&
        selected.lastModified === file.lastModified
      );

      if (!exists) {
        this.selectedFiles.push(file);
      }
    }

    input.value = '';
  }

  // =====================================================
  // ELIMINAR ARCHIVO
  // =====================================================

  removeFile(index: number): void {

    if (this.isUploading || this.isProcessing) {
      return;
    }

    this.selectedFiles.splice(index, 1);
  }

  // =====================================================
  // ENVIAR ARCHIVOS
  // =====================================================

  validateFiles(): void {

    if (this.selectedFiles.length === 0) {
      this.errorMessage =
        'Debes seleccionar al menos un archivo Excel.';
      return;
    }

    if (this.isUploading || this.isProcessing) {
      return;
    }

    this.errorMessage = '';
    this.issues = [];
    this.validationResult = null;
    this.showSuccessMessage = false;

    this.isUploading = true;

    this.pollingSubscription?.unsubscribe();

    this.validationApi.uploadFiles(this.selectedFiles).subscribe({

      next: response => {

      console.log('[FRONT] Archivos enviados:', response);

      this.isUploading = false;
      this.isProcessing = true;

      this.validationResult = response;

      this.cdr.detectChanges();

      this.startPolling(response.id);
    },
      error: error => {

        this.isUploading = false;
        this.isProcessing = false;

        console.error('Error enviando archivos:', error);

        const detail = error.error?.detail;

        this.errorMessage =
          typeof detail === 'string'
            ? detail
            : detail?.mensaje ||
              'No fue posible enviar los archivos al servidor.';
      }

    });
  }

  // =====================================================
  // CONSULTAR PROGRESO
  // =====================================================

  

private startPolling(validationId: string): void {

  const finalStates = [
    'COMPLETADO',
    'COMPLETADO_CON_OBSERVACIONES',
    'COMPLETADO_PARCIAL',
    'FALLIDO'
  ];

  this.isProcessing = true;
  this.isUploading = false;
  this.showSuccessMessage = false;

  this.cdr.detectChanges();

  this.pollingSubscription?.unsubscribe();

  this.pollingSubscription = timer(0, 2000)
    .pipe(
      switchMap(() =>
        this.validationApi.getValidation(validationId)
      ),
      takeWhile(
        response => !finalStates.includes(response.estado),
        true
      )
    )
    .subscribe({

      next: response => {

        console.log('[FRONT] Estado recibido:', response.estado);

        this.validationResult = response;
        this.isUploading = false;

        if (finalStates.includes(response.estado)) {

          console.log('[FRONT] Validación finalizada');

          this.isProcessing = false;

          this.showSuccessMessage =
            response.estado !== 'FALLIDO';

          this.cdr.detectChanges();

          this.loadIssues(validationId);

        } else {

          this.cdr.detectChanges();

        }

      },

      error: error => {

        console.error('[FRONT] Error consultando validación:', error);

        this.isUploading = false;
        this.isProcessing = false;

        this.errorMessage =
          'No fue posible consultar el estado de la validación.';

        this.cdr.detectChanges();

      },

      complete: () => {

        console.log('[FRONT] Consulta de estado finalizada');

        this.isUploading = false;
        this.isProcessing = false;

        this.cdr.detectChanges();

      }

    });
}



  // =====================================================
  // CONSULTAR ERRORES
  // =====================================================

  /*private loadIssues(validationId: string): void {

    this.isLoadingIssues = true;

    this.validationApi
      .getValidationErrors(validationId)
      .subscribe({

        next: response => {

          this.issues = response.items;

          this.isLoadingIssues = false;
        },

        error: error => {

          console.error('Error consultando incidencias:', error);

          this.isLoadingIssues = false;

          this.errorMessage =
            'La validación terminó, pero no fue posible consultar sus incidencias.';
        }

      });
  }*/

      

private loadIssues(validationId: string): void {

  console.log(
    '[FRONT] Iniciando consulta de incidencias:',
    validationId
  );

  this.isLoadingIssues = true;
  this.cdr.detectChanges();

  this.validationApi
    .getValidationErrors(validationId)
    .subscribe({

      next: response => {

        console.log(
          '[FRONT] Respuesta de incidencias:',
          response
        );

        this.issues = response.items ?? [];

        this.isLoadingIssues = false;

        console.log(
          '[FRONT] Total de incidencias:',
          this.issues.length
        );

        this.cdr.detectChanges();

      },

      error: error => {

        console.error(
          '[FRONT] Error consultando incidencias:',
          error
        );

        this.isLoadingIssues = false;

        this.errorMessage =
          'La validación terminó, pero no fue posible consultar sus incidencias.';

        this.cdr.detectChanges();

      }

    });
}



  // =====================================================
  // DESPLAZARSE A LOS RESULTADOS
  // =====================================================

  scrollToResults(): void {

    document
      .getElementById('validation-results')
      ?.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
  }

  // =====================================================
  // DESCARGAR REPORTE CONSOLIDADO
  // =====================================================

  downloadReport(): void {

    const validationId = this.validationResult?.id;

    if (!validationId) {
      return;
    }

    this.validationApi
      .downloadReport(validationId)
      .subscribe({

        next: blob => {

          this.saveBlob(
            blob,
            `reporte_validacion_${validationId}.xlsx`
          );
        },

        error: error => {

          console.error('Error descargando reporte:', error);

          this.errorMessage =
            'No fue posible descargar el reporte consolidado.';
        }

      });
  }

  // =====================================================
  // DESCARGAR EXCEL MARCADO
  // =====================================================

  downloadMarkedFile(filename: string): void {

    const validationId = this.validationResult?.id;

    if (!validationId || !filename) {
      return;
    }

    this.validationApi
      .downloadMarkedFile(validationId, filename)
      .subscribe({

        next: blob => {

          this.saveBlob(blob, filename);
        },

        error: error => {

          console.error('Error descargando Excel marcado:', error);

          this.errorMessage =
            'No fue posible descargar el Excel marcado.';
        }

      });
  }

  // =====================================================
  // GUARDAR ARCHIVO DESCARGADO
  // =====================================================

  private saveBlob(blob: Blob, filename: string): void {

    const url = window.URL.createObjectURL(blob);

    const link = document.createElement('a');

    link.href = url;
    link.download = filename;

    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);

    window.setTimeout(() => {
      window.URL.revokeObjectURL(url);
    }, 1000);
  }

  // =====================================================
  // DESTRUIR SUSCRIPCIONES
  // =====================================================

  ngOnDestroy(): void {

    this.pollingSubscription?.unsubscribe();
  }

}
