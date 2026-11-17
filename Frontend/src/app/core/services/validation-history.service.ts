
import { Injectable } from '@angular/core';

import { LocalValidationRecord } from '../models/validation-history.model';

@Injectable({
  providedIn: 'root'
})
export class ValidationHistoryService {

  private readonly dbName = 'snies-validator-db';
  private readonly storeName = 'validation-history';
  private readonly dbVersion = 1;

  /**
   * Abre la base de datos local.
   *
   * Si todavía no existe, IndexedDB crea la base de datos
   * y el almacén donde guardaremos las validaciones.
   */
  private openDatabase(): Promise<IDBDatabase> {

    return new Promise((resolve, reject) => {

      const request = indexedDB.open(this.dbName, this.dbVersion);

      request.onupgradeneeded = () => {

        const database = request.result;

        if (!database.objectStoreNames.contains(this.storeName)) {

          database.createObjectStore(this.storeName, {
            keyPath: 'id'
          });

        }

      };

      request.onsuccess = () => {
        resolve(request.result);
      };

      request.onerror = () => {
        reject(request.error);
      };

    });

  }

  /**
   * Guarda una validación completa.
   *
   * Si el identificador ya existe, actualiza el registro.
   */
  async save(record: LocalValidationRecord): Promise<void> {

    const database = await this.openDatabase();

    return new Promise((resolve, reject) => {

      const transaction = database.transaction(
        this.storeName,
        'readwrite'
      );

      const store = transaction.objectStore(this.storeName);

      store.put(record);

      transaction.oncomplete = () => {
        database.close();
        resolve();
      };

      transaction.onerror = () => {
        database.close();
        reject(transaction.error);
      };

      transaction.onabort = () => {
        database.close();
        reject(transaction.error);
      };

    });

  }

  /**
   * Recupera todas las validaciones guardadas.
   *
   * Las organiza desde la más reciente hasta la más antigua.
   */
  async getAll(): Promise<LocalValidationRecord[]> {

    const database = await this.openDatabase();

    return new Promise((resolve, reject) => {

      const transaction = database.transaction(
        this.storeName,
        'readonly'
      );

      const store = transaction.objectStore(this.storeName);

      const request = store.getAll();

      request.onsuccess = () => {

        const records = request.result as LocalValidationRecord[];

        records.sort((a, b) =>
          new Date(b.savedAt).getTime() -
          new Date(a.savedAt).getTime()
        );

        resolve(records);
      };

      request.onerror = () => {
        reject(request.error);
      };

      transaction.oncomplete = () => {
        database.close();
      };

      transaction.onerror = () => {
        database.close();
      };

    });

  }

  /**
   * Recupera una validación por su identificador.
   */
  async getById(id: string): Promise<LocalValidationRecord | null> {

    const database = await this.openDatabase();

    return new Promise((resolve, reject) => {

      const transaction = database.transaction(
        this.storeName,
        'readonly'
      );

      const store = transaction.objectStore(this.storeName);

      const request = store.get(id);

      request.onsuccess = () => {
        resolve(request.result ?? null);
      };

      request.onerror = () => {
        reject(request.error);
      };

      transaction.oncomplete = () => {
        database.close();
      };

      transaction.onerror = () => {
        database.close();
      };

    });

  }

  /**
   * Elimina una validación del historial local.
   */
  async delete(id: string): Promise<void> {

    const database = await this.openDatabase();

    return new Promise((resolve, reject) => {

      const transaction = database.transaction(
        this.storeName,
        'readwrite'
      );

      const store = transaction.objectStore(this.storeName);

      store.delete(id);

      transaction.oncomplete = () => {
        database.close();
        resolve();
      };

      transaction.onerror = () => {
        database.close();
        reject(transaction.error);
      };

      transaction.onabort = () => {
        database.close();
        reject(transaction.error);
      };

    });

  }

}
