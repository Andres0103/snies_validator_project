
import {
  Component,
  OnDestroy,
  ChangeDetectorRef,
  inject
} from '@angular/core';

import { EMPTY, Subscription, timer } from 'rxjs';
import { catchError, switchMap, takeWhile } from 'rxjs/operators';

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
  styleUrl: './validation.scss',
})
export class Validation implements OnDestroy {

  // =====================================================
  // DEPENDENCIAS
  // =====================================================

  // Servicio encargado de comunicarse con el backend.
  private readonly validationApi = inject(ValidationApiService);

  // Permite actualizar la vista cuando cambian los estados.
  private readonly cdr = inject(ChangeDetectorRef);

  // Suscripción utilizada para consultar periódicamente
  // el estado de una validación.
  private pollingSubscription?: Subscription;


  // =====================================================
  // ESTADO DEL COMPONENTE
  // =====================================================

  // Archivos que el usuario ha seleccionado para validar.
  selectedFiles: File[] = [];

  // Respuesta general del backend.
  validationResult: ValidationResponse | null = null;

  // Errores y advertencias encontrados durante la validación.
  issues: ValidationIssue[] = [];

  // Mensaje que se muestra cuando ocurre algún error.
  errorMessage = '';

  // Indica si los archivos están siendo enviados al backend.
  isUploading = false;

  // Indica si el backend está procesando los archivos.
  isProcessing = false;

  // Indica si se están consultando las incidencias.
  isLoadingIssues = false;

  // Controla la visualización del mensaje de éxito.
  showSuccessMessage = false;

  // Indica si el usuario está arrastrando archivos
  // sobre la zona de carga.
  isDragging = false;


  // =====================================================
  // SELECCIÓN DE ARCHIVOS MEDIANTE EL EXPLORADOR
  // =====================================================

  onFilesSelected(event: Event): void {

    const input = event.target as HTMLInputElement;

    // Si el usuario no seleccionó archivos, no hacemos nada.
    if (!input.files) {
      return;
    }

    // Reutilizamos la misma lógica de validación de archivos
    // que utilizaremos para Drag & Drop.
    this.addFiles(input.files);

    // Permite seleccionar nuevamente el mismo archivo
    // después de haberlo eliminado o procesado.
    input.value = '';
  }


  // =====================================================
  // AGREGAR Y VALIDAR ARCHIVOS
  // =====================================================

  private addFiles(files: FileList | File[]): void {

    // Convertimos FileList en un arreglo para poder recorrerlo.
    const selectedFiles = Array.from(files);

    // Solo aceptamos archivos con extensión .xlsx.
    const validFiles = selectedFiles.filter(file =>
      file.name.toLowerCase().endsWith('.xlsx')
    );

    // Al agregar archivos, ocultamos el mensaje de éxito anterior.
    this.showSuccessMessage = false;

    // Informamos si el usuario intentó agregar archivos
    // con extensiones diferentes de .xlsx.
    if (validFiles.length !== selectedFiles.length) {

      this.errorMessage =
        'Solo se permiten archivos Excel con extensión .xlsx.';

    } else {

      this.errorMessage = '';
    }

    // Incorporamos los archivos válidos evitando duplicados.
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

    // Actualizamos la vista.
    this.cdr.detectChanges();
  }


  // =====================================================
  // DRAG & DROP: ARRASTRAR ARCHIVOS
  // =====================================================

  onDragOver(event: DragEvent): void {

    // Evita que el navegador intente abrir el archivo
    // cuando se arrastra sobre la zona de carga.
    event.preventDefault();
    event.stopPropagation();

    // No permitimos arrastrar archivos durante
    // el envío o procesamiento de una validación.
    if (this.isUploading || this.isProcessing) {
      return;
    }

    // Activamos el estado visual de arrastre.
    this.isDragging = true;
  }


  // =====================================================
  // DRAG & DROP: SALIR DE LA ZONA DE CARGA
  // =====================================================

  onDragLeave(event: DragEvent): void {

    event.preventDefault();
    event.stopPropagation();

    // Desactivamos el estado visual de arrastre.
    this.isDragging = false;
  }


  // =====================================================
  // DRAG & DROP: SOLTAR ARCHIVOS
  // =====================================================

  onDrop(event: DragEvent): void {

    // Evitamos el comportamiento predeterminado del navegador.
    event.preventDefault();
    event.stopPropagation();

    // Desactivamos el estado visual de arrastre.
    this.isDragging = false;

    // Impedimos agregar archivos mientras se procesa
    // una validación.
    if (this.isUploading || this.isProcessing) {
      return;
    }

    // Recuperamos los archivos que el usuario soltó.
    const files = event.dataTransfer?.files;

    if (!files || files.length === 0) {
      return;
    }

    // Reutilizamos la misma validación de archivos.
    this.addFiles(files);
  }


  // =====================================================
  // ELIMINAR ARCHIVO SELECCIONADO
  // =====================================================

  removeFile(index: number): void {

    // No permitimos eliminar archivos mientras
    // se están enviando o procesando.
    if (this.isUploading || this.isProcessing) {
      return;
    }

    // Eliminamos el archivo correspondiente a su posición.
    this.selectedFiles.splice(index, 1);
  }


  // =====================================================
  // ENVIAR ARCHIVOS PARA VALIDACIÓN
  // =====================================================

  validateFiles(): void {

    // Comprobamos que exista al menos un archivo.
    if (this.selectedFiles.length === 0) {

      this.errorMessage =
        'Debes seleccionar al menos un archivo Excel.';

      return;
    }

    // Evitamos iniciar otra validación si ya existe
    // un proceso en ejecución.
    if (this.isUploading || this.isProcessing) {
      return;
    }

    // Limpiamos los mensajes y resultados anteriores
    // para iniciar una nueva validación.
    this.errorMessage = '';
    this.issues = [];
    this.validationResult = null;
    this.showSuccessMessage = false;

    // Activamos el estado de envío.
    this.isUploading = true;

    // Cancelamos cualquier consulta anterior.
    this.pollingSubscription?.unsubscribe();

    // Enviamos únicamente los archivos.
    // El backend identifica automáticamente sus plantillas.
    this.validationApi.uploadFiles(this.selectedFiles).subscribe({

      next: response => {

        console.log('[FRONT] Archivos enviados:', response);

        this.isUploading = false;
        this.isProcessing = true;

        // Guardamos la respuesta inicial del backend.
        this.validationResult = response;

        this.cdr.detectChanges();

        // Comenzamos a consultar el progreso.
        this.startPolling(response.id);
      },

      error: error => {

        this.isUploading = false;
        this.isProcessing = false;

        console.error('Error enviando archivos:', error);

        const detail = error.error?.detail;

        // Mostramos el mensaje devuelto por el backend
        // o uno genérico si no existe.
        this.errorMessage =
          typeof detail === 'string'
            ? detail
            : detail?.mensaje ||
              'No fue posible enviar los archivos al servidor.';

        this.cdr.detectChanges();
      }

    });
  }


  // =====================================================
  // CONSULTAR PROGRESO DE LA VALIDACIÓN
  // =====================================================

  private startPolling(validationId: string): void {

    // Estados que indican que el backend terminó
    // de procesar la solicitud.
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

    // Cancelamos cualquier consulta anterior.
    this.pollingSubscription?.unsubscribe();

    // Consultamos el estado inmediatamente y después
    // repetimos la consulta cada dos segundos.
    this.pollingSubscription = timer(0, 2000)
      .pipe(

        switchMap(() =>
          this.validationApi.getValidation(validationId).pipe(

            // Si ocurre un error temporal consultando el estado,
            // evitamos interrumpir inmediatamente el polling.
            catchError(error => {

              console.error(
                '[FRONT] Error temporal consultando validación:',
                error
              );

              return EMPTY;
            })

          )
        ),

        // Continuamos consultando mientras el estado
        // no sea uno de los estados finales.
        // El true permite recibir también la respuesta final.
        takeWhile(
          response => !finalStates.includes(response.estado),
          true
        )

      )
      .subscribe({

        next: response => {

          console.log('[FRONT] Estado recibido:', response.estado);

          // Actualizamos los datos recibidos del backend.
          this.validationResult = response;

          this.isUploading = false;

          // =================================================
          // VALIDACIÓN FINALIZADA
          // =================================================

          if (finalStates.includes(response.estado)) {

            console.log('[FRONT] Validación finalizada');

            this.isProcessing = false;

            // Mostramos éxito siempre que el proceso
            // no haya terminado en estado FALLIDO.
            this.showSuccessMessage =
              response.estado !== 'FALLIDO';

            // Limpiamos los archivos seleccionados para
            // permitir iniciar una nueva validación.
            //
            // IMPORTANTE:
            // No eliminamos validationResult porque debemos
            // conservar los resultados de esta validación.
            this.selectedFiles = [];

            this.isDragging = false;

            this.cdr.detectChanges();

            // Consultamos las incidencias de esta validación.
            this.loadIssues(validationId);

            // Nos desplazamos automáticamente hasta
            // los resultados únicamente al finalizar.
            //
            // Esperamos a que Angular actualice la vista
            // antes de ejecutar el desplazamiento.
            window.setTimeout(() => {
              this.scrollToResults();
            }, 200);

          } else {

            // Mientras continúa el procesamiento,
            // actualizamos la vista sin desplazarnos.
            this.cdr.detectChanges();
          }

        },

        error: error => {

          console.error(
            '[FRONT] Error consultando validación:',
            error
          );

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
  // CONSULTAR ERRORES Y ADVERTENCIAS
  // =====================================================

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

          // Guardamos las incidencias recibidas.
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
  // DESPLAZARSE AUTOMÁTICAMENTE A LOS RESULTADOS
  // =====================================================

  scrollToResults(): void {

    // Buscamos el contenedor de resultados en el HTML.
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

    // Recuperamos el identificador de la validación actual.
    const validationId = this.validationResult?.id;

    if (!validationId) {
      return;
    }

    this.validationApi
      .downloadReport(validationId)
      .subscribe({

        next: blob => {

          // Guardamos el reporte descargado.
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

          // Guardamos el Excel marcado.
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

    // Creamos una URL temporal para el archivo descargado.
    const url = window.URL.createObjectURL(blob);

    const link = document.createElement('a');

    link.href = url;
    link.download = filename;

    // Agregamos el enlace al documento para ejecutar
    // la descarga automáticamente.
    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);

    // Liberamos la URL temporal para evitar consumir memoria.
    window.setTimeout(() => {
      window.URL.revokeObjectURL(url);
    }, 1000);
  }


  // =====================================================
  // DESTRUIR SUSCRIPCIONES
  // =====================================================

  ngOnDestroy(): void {

    // Cancelamos las consultas pendientes cuando
    // el usuario abandona el componente.
    this.pollingSubscription?.unsubscribe();
  }

}
