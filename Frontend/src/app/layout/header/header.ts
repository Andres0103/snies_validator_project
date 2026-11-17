
import { Component, signal } from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router } from '@angular/router';
import { filter, startWith } from 'rxjs';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [],
  templateUrl: './header.html',
  styleUrl: './header.scss',
})
export class Header {

  pageTitle = signal('Panel principal');

  pageDescription = signal(
    'Sistema de gestión y validación de información SNIES'
  );

  constructor(
    private router: Router,
    private activatedRoute: ActivatedRoute
  ) {
    this.router.events
      .pipe(
        filter(
          (event): event is NavigationEnd =>
            event instanceof NavigationEnd
        ),
        startWith(null)
      )
      .subscribe(() => {
        this.updateHeader();
      });
  }

  private updateHeader(): void {
    let route = this.activatedRoute;

    // Buscamos la ruta más profunda activa.
    while (route.firstChild) {
      route = route.firstChild;
    }

    // Obtenemos la información configurada en app.routes.ts.
    const routeData = route.snapshot.data;

    this.pageTitle.set(
      routeData['headerTitle'] ?? 'SNIES Validator'
    );

    this.pageDescription.set(
      routeData['headerDescription'] ??
      'Sistema de gestión y validación de información SNIES'
    );
  }
}
