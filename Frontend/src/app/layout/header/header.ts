
import { Component, OnDestroy, signal } from '@angular/core';
import { NavigationEnd, Router, ActivatedRouteSnapshot } from '@angular/router';
import { filter, startWith, Subscription } from 'rxjs';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [],
  templateUrl: './header.html',
  styleUrl: './header.scss',
})
export class Header implements OnDestroy {

  // Título que se muestra en el encabezado.
  pageTitle = signal('Panel principal');

  // Descripción que se muestra debajo del título.
  pageDescription = signal(
    'Sistema de gestión y validación de información SNIES'
  );

  // Guardamos la suscripción para liberarla cuando se destruya el componente.
  private routerSubscription?: Subscription;

  constructor(private router: Router) {

    // Actualizamos el encabezado cada vez que termina una navegación.
    this.routerSubscription = this.router.events
      .pipe(
        filter(
          (event): event is NavigationEnd =>
            event instanceof NavigationEnd
        ),

        // También ejecutamos la actualización al inicializar el componente.
        startWith(null)
      )
      .subscribe(() => {
        this.updateHeader();
      });
  }

  /**
   * Obtiene los datos de la ruta activa y actualiza
   * el título y la descripción del encabezado.
   */
  private updateHeader(): void {

    // Empezamos desde la raíz del árbol de rutas.
    let route: ActivatedRouteSnapshot =
      this.router.routerState.snapshot.root;

    // Guardamos los datos encontrados durante el recorrido.
    // Las rutas más profundas podrán sobrescribir los valores anteriores.
    let routeData = { ...route.data };

    // Recorremos el árbol hasta encontrar la ruta más profunda.
    while (route.firstChild) {

      route = route.firstChild;

      // Incorporamos los datos de cada ruta.
      routeData = {
        ...routeData,
        ...route.data
      };
    }

    // Actualizamos el título.
    this.pageTitle.set(
      routeData['headerTitle'] ?? 'SNIES Validator'
    );

    // Actualizamos la descripción.
    this.pageDescription.set(
      routeData['headerDescription'] ??
      'Sistema de gestión y validación de información SNIES'
    );
  }

  /**
   * Liberamos la suscripción para evitar fugas de memoria.
   */
  ngOnDestroy(): void {
    this.routerSubscription?.unsubscribe();
  }
}
