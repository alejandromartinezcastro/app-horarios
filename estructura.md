timetable-app/
  README.md
  .gitignore
  .env.example
  docker-compose.yml

  backend/
    pyproject.toml
    alembic.ini
    src/
      app/
        __init__.py
        main.py

        settings.py
        logging.py

        api/
          __init__.py
          deps.py
          routers/
            __init__.py
            health.py
            solve.py
            projects.py

        services/
          __init__.py
          solver_service.py
          project_service.py

        domain/
          __init__.py

          core/
            __init__.py
            schema.py
            validate.py
            io.py

          calendar/
            __init__.py
            build_slots.py

          solver/
            __init__.py
            solve.py

        infra/
          __init__.py

          db/
            __init__.py
            session.py
            models.py

          migrations/
            env.py
            versions/

    tests/
      test_validate.py
      test_solve_smoke.py
      test_projects.py

  frontend/
    package.json
    tsconfig.json
    next.config.js
    .env.local.example

    src/
      app/
        layout.tsx
        page.tsx
        projects/
          page.tsx
          [id]/
            page.tsx

      components/
        Wizard/
          WizardShell.tsx
          steps/
            CalendarStep.tsx
            GroupsStep.tsx
            SubjectsStep.tsx
            TeachersStep.tsx
            RoomsStep.tsx
            RequirementsStep.tsx
            ReviewSolveStep.tsx

        Timetable/
          TimetableGrid.tsx
          GroupView.tsx
          TeacherView.tsx
          RoomView.tsx

        ui/                 # (shadcn/ui si lo usas)

      lib/
        api.ts              # cliente fetch al backend
        problem.ts          # tipos TS + zod
        normalize.ts        # helpers de mapeo JSON <-> UI
        slots.ts            # helpers de slots / etiquetas

      styles/
        globals.css
