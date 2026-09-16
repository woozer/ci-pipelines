# Pipelinekeuzes: naslag

Voor dagelijks gebruik volstaan de [drie handelingen](../README.md#dagelijks-gebruik). Bouwen en verplichte tests starten direct. De applicatie neemt het gedeelde [formulier New pipeline](../config/pipeline-inputs.yml) en één [centrale pipeline](../templates/java-service.yml) op, beide met dezelfde uitgebrachte pipelineversie. De vaste moduleversies worden beheerd door `ci-pipelines`. Alleen `maven-project` is een verplichte vaste componentinput. Formulierwaarden worden doorgegeven zonder standaardwaarden te herhalen.

De pipelinenamen gebruiken GitLabs [`workflow:name`](https://docs.gitlab.com/ci/yaml/#workflowname): `CI — <branch>`, **Dev — deployment en integratietests** en `Release — <version>`. Na reservering wordt de versie vastgelegd in de release-childconfiguratie. Triggers nemen geen variabelen van de parent over, zodat de parentnaam de childnaam niet overschrijft.

## Kiezen vóór het starten

Selecteer op **Build > Pipelines > New pipeline** de branch en de onderstaande inputs. Pipelines die door een push starten, gebruiken de standaardwaarden.

| Input | Standaardwaarde | Effect |
|---|---|---|
| `cluster` | `local` | Eerste keuze voor het dev-cluster |
| `user_config` | `default` | Eerste keuze voor aanvullende Helm-values |
| `pipeline_mode` | `deploy` | Bepaalt welke jobs worden opgenomen |

| Modus | Jobs op protected main |
|---|---|
| `validate` | Backend/UI bouwen en verplichte tests uitvoeren; optionele extra backendtest |
| `publish` | Daarnaast Maven-packages, backend/UI-images en Helm-charts publiceren |
| `deploy` | Daarnaast deploymentinstellingen kiezen, Helm uitvoeren en de deployment testen; **start-release** beschikbaar maken |

Featurebranches en merge requests voeren alleen builds en tests uit. `pipeline_mode` ligt vast zodra de pipeline wordt aangemaakt. Dit volgt GitLabs model voor configuratie-inputs: jobinputs kunnen tijdens de uitvoering geen `rules` wijzigen of stages toevoegen. Zie [het bereik van inputs](https://docs.gitlab.com/ci/inputs/) en [beperkingen van jobinputs](https://docs.gitlab.com/ci/jobs/job_inputs/#where-you-can-use-job-inputs).

## Tests kiezen tijdens ontwikkeling

Open **test-custom** door op de jobnaam te klikken. Kies `not @ui and not @ignore` voor de volledige backendsuite of `@smoke and not @ui`, en klik op **Run job**. De begroetingstest heeft de tag `@smoke`. De backendsuite controleert ook health, dieren en een 404-antwoord voor een onbekend endpoint. Gebruik **Retry job with modified values** voor een andere selectie. De gekozen expressie staat in het outputartifact als `CUCUMBER_TEST_TAGS`. Zie [GitLab-jobinputs](https://docs.gitlab.com/ci/jobs/job_inputs/).

Deze optionele ontwikkeljob telt niet als verplichte validatie voor een merge of release. De verplichte job **test** en de releasetests voeren altijd hun volledige ingestelde suite uit. Browserscenario's draaien apart in **cucumber-ui**, zodra beide deployments gereed zijn. Een pipeline kan groen zijn terwijl de optionele test faalt; bekijk daarom de status en het rapport van die job zelf.

Deze keuze selecteert Cucumber-scenario's. Het is geen Spring- of Maven-profiel. De losse Cucumber-component ondersteunt wel de optionele Maven-input `profile`. Voeg eerst echte applicatieprofielen toe voordat je die als keuzes aanbiedt. Dezelfde smokeselectie werkt lokaal met `./mvnw -Dcucumber.filter.tags="@smoke and not @ui" verify`.

## Deployment kiezen na publicatie

**configure-deploy** wordt ingepland zodra images en charts zijn gepubliceerd. De wachttijd van tien seconden begint op dat moment. Zonder gebruikersactie gelden de aanvankelijk gekozen waarden voor `cluster` en `user_config`. De beschikbaarheid van een runner bepaalt wanneer de job daadwerkelijk start.

Kies vóór het verstrijken van de timer **Unschedule**, open de job en start deze met de gewenste inputs. Na **Unschedule** blijft de timer gestopt tot de gebruiker de job start. Dit is onze gebruiksafspraak op basis van GitLabs uitgestelde jobs; er verschijnt geen automatische popup. Zie [uitgestelde jobs](https://docs.gitlab.com/ci/jobs/job_control/#run-a-job-after-a-delay).

**deploy-dev** start één childpipeline met **helm-deploy** en **cucumber-dev**. Deze gebruikt de interne [deploymentconfiguratie](../internal/java-deploy.yml) en haalt image-digest en chartreferentie op uit de exacte parentpipeline. De parenttrigger houdt de dev-lock vast tot beide jobs klaar zijn. Zie [artifacts van parentpipelines](https://docs.gitlab.com/ci/yaml/#needspipelinejob) en [resourcegroepen](https://docs.gitlab.com/ci/resource_groups/).

Met `ui-directory` deployt de childpipeline ook de UI en voert hij **cucumber-ui** uit. Beide Cucumber-jobs wachten op beide geslaagde Helm-deployments. Dit geldt ook voor releases. De tests tijdens de build worden nog steeds vóór de deployment uitgevoerd.

## Wachten op gezonde deployments

Helm wacht op gereedheid en voert bij fouten een rollback uit. Kubernetes controleert de backend via `/actuator/health/readiness` en de UI via `/healthz`, met `periodSeconds: 10`. Een container die nog niet gereed is, kan vaker worden gecontroleerd. Gezonde endpoints geven HTTP 200 terug. De charts gebruiken `maxUnavailable: 0`, zodat tijdens de rollout alle gewenste replica's gereed moeten komen. Er is geen apart CI-pollingscript nodig. Zie [Kubernetes-probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) en [Helm upgrade](https://helm.sh/docs/helm/helm_upgrade/).

De optionele input `deployment-timeout` van de centrale pipeline is standaard `5m` per Helm-deployment. Voeg alleen de afwijkende waarde toe aan de bestaande java-service-include:

```yaml
inputs:
  # Keep the existing required inputs here.
  deployment-timeout: 8m
```

Deze instelling wordt doorgegeven aan de deployment- en release-childpipelines. Het is een timeout voor de Helm-bewerking; niet voor de hele pipeline. Een rollback kan extra tijd kosten. Houd voldoende ruimte onder de standaard joblimiet van 30 minuten. De losse component `helm-deploy` heeft afzonderlijke inputs `timeout` en `job-timeout`. Als Helm faalt of een timeout bereikt, starten de integratietests niet, ook niet als de rollback de vorige gezonde versie herstelt.

Readiness controleert of elk proces beschikbaar is. De UI-healthcheck roept de backend niet aan. Cucumber en Playwright controleren de volledige interactie tussen UI en backend nadat beide processen gereed zijn. Liveness blijft onafhankelijk van externe diensten, volgens [Spring Boots probeadvies](https://docs.spring.io/spring-boot/reference/actuator/endpoints.html#actuator.endpoints.kubernetes-probes).

## Dezelfde build met andere values deployen

1. Open **configure-deploy** in de geslaagde pipeline en kies **Retry job with modified values**.
2. Kies een ander Helm-gebruikersprofiel en wacht tot de job slaagt.
3. Kies **Run again** bij de trigger **deploy-dev**. Dit maakt de volledige deployment-childpipeline opnieuw aan, inclusief Cucumber-tests en onder dezelfde lock.

Alleen de keuzejob opnieuw uitvoeren herstart geen afgeronde vervolgjob. Image en chart worden hergebruikt; build en publicatie draaien niet opnieuw. De artifacts van de parentjobs moeten nog beschikbaar zijn; de standaardbewaartermijn is zeven dagen. Zie [een downstream-pipeline opnieuw aanmaken](https://docs.gitlab.com/ci/pipelines/downstream_pipelines/#recreate-a-downstream-pipeline).

## Helm-bestanden en toegangsgegevens

```text
environment/
  cluster/local.yaml
  user/default.yaml
  user/two-replicas.yaml
```

Helm past eerst de chartdefaults toe, daarna de clusterwaarden en ten slotte de gebruikerswaarden. De expliciete image-digest blijft doorslaggevend. Het profiel `default` is leeg; `two-replicas` stelt het aantal replica's op twee in.

Alleen het cluster `local` is ingericht. Het is centraal gekoppeld aan `LOCAL_KUBECONFIG` en de dev-URL's. Toegangsgegevens staan in GitLab-variabelen, nooit in values-bestanden. Richt eerst credentials en een centrale koppeling in voordat je een ander cluster aanbiedt. De keuzelijst is expliciet geconfigureerd; GitLab leidt de opties niet af uit mappen.
