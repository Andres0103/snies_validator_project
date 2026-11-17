
import {
  Component,
  OnDestroy,
  ChangeDetectorRef,
  inject
} from '@angular/core';

import {
  EMPTY,
  Subscription,
  timer,
  firstValueFrom
} from 'rxjs';

import {
  catchError,
  switchMap,
  takeWhile
} from 'rxjs/operators';

// Servicio que se comunica con el backend.
import { ValidationApiService } from '../../core/services/validation-api.service';

// Servicio que administra el historial local en IndexedDB.
import { ValidationHistoryService } from '../../core/services/validation-history.service';

// Modelos de las respuestas del backend.
import {
  ValidationResponse,
  ValidationIssue
} from '../../core/models/validation.model';

// Modelos del historial local.
import {
  LocalValidationRecord,
  StoredValidationFile
} from '../../core/models/validation-history.model';


@Component({
  selector: 'app-validation',
  standalone: true,
  imports: [],
  templateUrl: './validation.html',
  styleUrl: './validation.scss'
})
export class Validation implements OnDestroy {

  // =====================================================
  // DEPENDENCIAS
  // =====================================================

  // Servicio encargado de enviar archivos y consultar
  // los resultados de las validaciones en el backend.
  private readonly validationApi = inject(ValidationApiService);

  // Servicio encargado de guardar y consultar
  // los registros del historial en IndexedDB.
  private readonly historyService = inject(ValidationHistoryService);

  // Permite actualizar la vista cuando cambian
  // los estados de las operaciones asíncronas.
  private readonly cdr = inject(ChangeDetectorRef);

  // Suscripción utilizada para consultar periódicamente
  // el estado de una validación.
  private pollingSubscription?: Subscription;


  // =====================================================
  // ESTADO DEL COMPONENTE
  // =====================================================

  // Archivos que el usuario ha seleccionado.
  selectedFiles: File[] = [];

  // Respuesta general de la validación actual.
  validationResult: ValidationResponse | null = null;

  // Errores y advertencias encontrados.
  issues: ValidationIssue[] = [];

  // Mensaje que se muestra cuando ocurre un error.
  errorMessage = '';

  // Indica si los archivos están siendo enviados.
  isUploading = false;

  // Indica si el backend está procesando los archivos.
  isProcessing = false;

  // Indica si se están consultando las incidencias.
  isLoadingIssues = false;

  // Controla la visualización del mensaje de éxito.
  showSuccessMessage = false;

  // Indica si el usuario está arrastrando archivos.
  isDragging = false;

  // Indica si se está guardando el historial local.
  isSavingHistory = false;

  // Conserva los archivos originales de la validación actual.
  // Es importante porque selectedFiles se limpia al finalizar.
  private originalFilesForCurrentValidation: File[] = [];


  // =====================================================
  // SELECCIÓN DE ARCHIVOS MEDIANTE EL EXPLORADOR
  // =====================================================

  onFilesSelected(event: Event): void {

    const input = event.target as HTMLInputElement;

    // Si el usuario no seleccionó archivos, no hacemos nada.
    if (!input.files) {
      return;
    }

    // Reutilizamos la misma lógica de validación
    // que utilizamos para Drag & Drop.
    this.addFiles(input.files);

    // Permite seleccionar nuevamente el mismo archivo
    // después de haberlo eliminado.
    input.value = '';
  }


  // =====================================================
  // AGREGAR Y VALIDAR ARCHIVOS
  // =====================================================

  private addFiles(files: FileList | File[]): void {

    // Convertimos FileList en un arreglo.
    const receivedFiles = Array.from(files);

    // Solo aceptamos archivos con extensión .xlsx.
    const validFiles = receivedFiles.filter(file =>
      file.name.toLowerCase().endsWith('.xlsx')
    );

    // Ocultamos el mensaje de éxito anterior.
    this.showSuccessMessage = false;

    // Informamos si se intentaron agregar archivos
    // con extensiones diferentes de .xlsx.
    if (validFiles.length !== receivedFiles.length) {

      this.errorMessage =
        'Solo se permiten archivos Excel con extensión .xlsx.';

    } else {

      this.errorMessage = '';
    }

    // Agregamos los archivos válidos evitando duplicados.
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

    // Evitamos el comportamiento predeterminado.
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

    // No permitimos eliminar archivos durante
    // el envío o procesamiento.
    if (this.isUploading || this.isProcessing) {
      return;
    }

    // Eliminamos el archivo correspondiente.
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

    // Limpiamos los mensajes y resultados anteriores.
    this.errorMessage = '';
    this.issues = [];
    this.validationResult = null;
    this.showSuccessMessage = false;

    // Conservamos una copia de los archivos originales.
    // Los necesitaremos para guardar el historial local.
    // No debemos depender de selectedFiles porque se limpia
    // cuando termina el procesamiento.
    this.originalFilesForCurrentValidation = [
      ...this.selectedFiles
    ];

    // Activamos el estado de envío.
    this.isUploading = true;

    // Cancelamos cualquier consulta anterior.
    this.pollingSubscription?.unsubscribe();

    // Enviamos únicamente los archivos.
    // El backend detecta automáticamente sus plantillas.
    this.validationApi.uploadFiles(this.selectedFiles).subscribe({

      next: response => {

        console.log('[FRONT] Archivos enviados:', response);

        this.isUploading = false;
        this.isProcessing = true;

        // Guardamos la respuesta inicial.
        this.validationResult = response;

        this.cdr.detectChanges();

        // Comenzamos a consultar el progreso.
        this.startPolling(response.id);
      },

      error: error => {

        this.isUploading = false;
        this.isProcessing = false;

        // No se inició una validación correctamente.
        // Liberamos la copia temporal de los archivos.
        this.originalFilesForCurrentValidation = [];

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

    // Estados que indican que el backend terminó.
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

          console.log(
            '[FRONT] Estado recibido:',
            response.estado
          );

          // Actualizamos los datos recibidos del backend.
          this.validationResult = response;

          this.isUploading = false;

          // =============================================
          // VALIDACIÓN FINALIZADA
          // =============================================

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
            // La copia original permanece disponible
            // para guardarla en el historial.
            this.selectedFiles = [];

            this.isDragging = false;

            this.cdr.detectChanges();

            // Consultamos las incidencias.
            // Cuando termine esta consulta se guardará
            // la validación completa en IndexedDB.
            this.loadIssues(validationId);

            // Nos desplazamos automáticamente
            // hasta los resultados.
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

          console.log(
            '[FRONT] Consulta de estado finalizada'
          );

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

          // Una vez recuperadas las incidencias,
          // guardamos la validación completa localmente.
          void this.saveValidationToHistory(validationId);
        },

        error: error => {

          console.error(
            '[FRONT] Error consultando incidencias:',
            error
          );

          this.isLoadingIssues = false;
          this.issues = [];

          this.errorMessage =
            'La validación terminó, pero no fue posible consultar sus incidencias. Se guardará el historial sin ellas.';

          this.cdr.detectChanges();

          // Aunque falle la consulta de incidencias,
          // intentamos guardar el resumen y los archivos.
          void this.saveValidationToHistory(validationId);
        }

      });
  }


  // =====================================================
  // GUARDAR VALIDACIÓN COMPLETA EN INDEXEDDB
  // =====================================================

  private async saveValidationToHistory(
    validationId: string
  ): Promise<void> {

    // Recuperamos el resultado de la validación actual.
    const validation = this.validationResult;

    // Comprobamos que exista y corresponda al identificador.
    if (!validation || validation.id !== validationId) {
      return;
    }

    // Evitamos guardar dos veces simultáneamente.
    if (this.isSavingHistory) {
      return;
    }

    this.isSavingHistory = true;

    this.cdr.detectChanges();

    console.log(
      '[FRONT] Iniciando almacenamiento local:',
      validationId
    );

    try {

      // ===============================================
      // 1. GUARDAR ARCHIVOS ORIGINALES
      // ===============================================

      // Los archivos originales siguen disponibles
      // gracias a la copia realizada antes del envío.
      const originalFiles: StoredValidationFile[] =
        this.originalFilesForCurrentValidation.map(file => ({

          name: file.name,

          type: file.type ||
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',

          blob: file

        }));


      // ===============================================
      // 2. RECUPERAR EXCEL MARCADOS
      // ===============================================

      // Descargamos los archivos generados por el backend
      // para conservarlos localmente.
      const generatedFiles = await Promise.all(

        validation.archivos
          .filter(file => !!file.archivo_marcado)
          .map(async file => {

            try {

              const filename = file.archivo_marcado!;

              const blob = await firstValueFrom(
                this.validationApi.downloadMarkedFile(
                  validationId,
                  filename
                )
              );

              return {

                name: filename,

                type: blob.type ||
                  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',

                blob

              } as StoredValidationFile;

            } catch (error) {

              // Un archivo marcado puede fallar individualmente.
              // Esto no debe impedir guardar los demás.
              console.error(
                '[FRONT] No fue posible recuperar el Excel marcado:',
                file.archivo_marcado,
                error
              );

              return null;
            }

          })

      );

      // Conservamos únicamente los archivos recuperados.
      const availableGeneratedFiles = generatedFiles.filter(
        (file): file is StoredValidationFile => file !== null
      );


      // ===============================================
      // 3. RECUPERAR REPORTE CONSOLIDADO
      // ===============================================

      let report: StoredValidationFile | null = null;

      // Si el proceso terminó completamente fallido,
      // no intentamos descargar un reporte.
      if (validation.estado !== 'FALLIDO') {

        try {

          const blob = await firstValueFrom(
            this.validationApi.downloadReport(validationId)
          );

          report = {

            name: `reporte_validacion_${validationId}.xlsx`,

            type: blob.type ||
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',

            blob

          };

        } catch (error) {

          // El historial puede conservarse aunque
          // no esté disponible el reporte consolidado.
          console.warn(
            '[FRONT] No fue posible recuperar el reporte:',
            error
          );

        }

      }


      // ===============================================
      // 4. CONSTRUIR EL REGISTRO LOCAL
      // ===============================================

      const record: LocalValidationRecord = {

        // Conservamos todos los datos que devuelve el backend.
        ...validation,

        // Fecha y hora en que guardamos el registro local.
        savedAt: new Date().toISOString(),

        // Archivos originales.
        originalFiles,

        // Archivos marcados recuperados.
        generatedFiles: availableGeneratedFiles,

        // Reporte consolidado.
        report,

        // Incidencias de la validación.
        issues: [...this.issues]

      };


      // ===============================================
      // 5. GUARDAR EN INDEXEDDB
      // ===============================================

      await this.historyService.save(record);

      console.log(
        '[FRONT] Validación guardada correctamente:',
        validationId
      );

      // Liberamos la copia temporal porque IndexedDB
      // ya conserva los archivos originales.
      this.originalFilesForCurrentValidation = [];

    } catch (error) {

      console.error(
        '[FRONT] Error guardando historial local:',
        error
      );

      this.errorMessage =
        'La validación terminó, pero no fue posible guardar el historial local.';

      // Conservamos la copia temporal de los archivos
      // si el almacenamiento falla, para no perderla
      // antes de que termine la sesión del componente.
    } finally {

      this.isSavingHistory = false;

      this.cdr.detectChanges();
    }

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

          // Guardamos el reporte descargado en el equipo.
          this.saveBlob(
            blob,
            `reporte_validacion_${validationId}.xlsx`
          );
        },

        error: error => {

          console.error(
            'Error descargando reporte:',
            error
          );

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

          // Guardamos el Excel marcado en el equipo.
          this.saveBlob(blob, filename);
        },

        error: error => {

          console.error(
            'Error descargando Excel marcado:',
            error
          );

          this.errorMessage =
            'No fue posible descargar el Excel marcado.';
        }

      });
  }


  // =====================================================
  // GUARDAR ARCHIVO DESCARGADO
  // =====================================================

  private saveBlob(blob: Blob, filename: string): void {

    // Creamos una URL temporal para el archivo.
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
