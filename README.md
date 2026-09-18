# Standaardpipelines voor GitLab

Gebruik `java-service` voor een Java-applicatie met één deploybare Maven-module en eventueel een Angular-UI. De pipeline combineert build, unit- en integratietests, scans, publicatie, Helm-deployment en een handmatige releaseknop. Een Maven-reactor mag daarnaast libraries en testmodules bevatten.

Dit project heeft een eigen versie. De losse bouwblokken blijven zelfstandig beschikbaar in [ci-components](https://github.com/woozer/ci-components). Versie `1.1.0` van deze pipeline gebruikt die bouwblokken op **`2.0.0`**. Afnemers kiezen één pipelineversie; de beheerder test en onderhoudt de combinatie.

## Gebruiken

Na installatie staat `java-service` onder **ci-pipelines** in de [lokale CI/CD Catalog](http://localhost:8929/explore/catalog). Het minimale applicatiebestand is:

```yaml
include:
  - component: $CI_SERVER_FQDN/root/ci-pipelines/java-service@1.1.0
    inputs:
      maven-project: hello-app
```

`maven-project` is de enige verplichte componentinput. Geef `ui-directory: ui` mee voor de aparte frontend. Optionele defaults hoef je niet te herhalen. De catalogus en [componentdefinitie](templates/java-service.yml) beschrijven de beschikbare inputs. De applicatie levert de POM, broncode, Helm-charts en `environment/cluster/`- en `environment/user/`-values.

Voor het formulier op **New pipeline** neem je ook [config/pipeline-inputs.yml](config/pipeline-inputs.yml) op met dezelfde **pipelineversie**. Zie het [volledige applicatievoorbeeld](examples/application.gitlab-ci.yml). De standaardpipeline kiest zelf de moduleversies; er is geen verplichte `library-ref` meer.

De platformbeheerder regelt runners, images, registries, SonarQube en toegangsgegevens. De lokale defaults komen uit `ci-components@2.0.0/config/organization.yml`; groeps- en projectvariabelen kunnen deze overschrijven. Voor een nieuwe Docker-demo volg je de [installatiehandleiding](https://github.com/woozer/ci-components/blob/main/installation.md). Voor organisatiediensten en OpenShift: [platforminrichting](https://github.com/woozer/ci-components/blob/main/docs/real-environment.md).

## Dagelijks gebruik

1. **Bouwen:** push een branch of merge een beoordeelde MR. Op protected `main` volgen publicatie, dev-deployment en API-/browsertests.
2. **Ander Helm-profiel:** voer **configure-deploy** opnieuw uit met de gewenste waarden en kies daarna **Run again** bij **deploy-dev**. Bij de eerste uitvoering gelden na tien seconden de defaults; kies tijdig **Unschedule** om andere waarden in te vullen.
3. **Release:** gebruik **start-release** na groene dev-validatie. **publish-release** legt de release met artifactlinks vast nadat de releaseartifacts zijn gebouwd en in dev zijn getest.

Lees [pipelinekeuzes](docs/pipeline-options.md), [releasebeleid](docs/releases.md) en [deploymentlocks](docs/deployment-concurrency.md) voor de werking.

## Samenstelling en versies

`templates/java-service.yml` is de openbare cataloguscomponent. `internal/java-build.yml`, `internal/java-deploy.yml` en `internal/java-release.yml` verdelen het onderhoud. Ze zijn geen afzonderlijke cataloguscomponenten. `shared/java-service.yml` bevat de gedeelde Maven-cache-instellingen.

De taakcomponenten worden opgenomen met `include:component` en een vaste versie. De kleine organisatie- en Helm-configuratie wordt met `include:project` op dezelfde componentversie geladen. Deployment- en release-childpipelines gebruiken automatisch de commit van de opgenomen pipelinecomponent via GitLabs `component.sha`. Daardoor kan een nieuwere `main` een lopende pipeline niet veranderen.

GitLab ondersteunt samengestelde componenten en adviseert [vaste versies voor externe afhankelijkheden](https://docs.gitlab.com/ci/components/#manage-dependencies). Onze verdeling over twee bibliotheekprojecten is een beheerkeuze. Deze complete pipeline bepaalt bewust `workflow`, `stages` en defaults; neem hem eenmaal op als eigenaar van de applicatiepipeline. Wie zelf de volgorde wil bepalen, gebruikt de [losse modules](https://github.com/woozer/ci-components/blob/main/docs/modules.md).

Alle bouwblokken binnen deze pipeline gebruiken dezelfde `ci-components`-versie, omdat ze gedeelde verborgen jobs hebben. Upgrade hun verwijzingen samen, test de combinatie en publiceer daarna een nieuwe pipelineversie. Bestaande tags blijven intact. Publiceer alleen een nieuwe SemVer-tag op een beoordeelde commit van protected `main`.

## Testen en publiceren

`validate-pipelines` controleert onder meer doorgifte van instellingen, artifactafhankelijkheden, outputnamen, deploymentlocks en de vastgezette componentversies. `validate-sample` start via een standaard multi-projecttrigger **ci-samples** met de exacte kandidaat-SHA. De sample voert de publieke component uit in modus `validate`: Maven-build en unittests, Cucumber, npm-build/tests, Dependency-Check en Sonar met quality gate. Hij deployt geen applicatie en maakt geen applicatierelease. De volledige delivery wordt in **hello-world** gevalideerd.

Voor handmatige validatie kies je in **ci-samples → New pipeline** `sample: java-service` en een uitgebrachte versie of kandidaat-SHA bij `pipeline_ref`. De negentien losse modulevoorbeelden blijven onder `sample: all` beschikbaar en gebruiken hun eigen `library_ref`.

De projectpipeline vereist `CI_VALIDATION_IMAGE`, `CI_RELEASE_IMAGE` en `CI_SAMPLES_PROJECT`. De demo-installer richt die in, inclusief runner en job-tokenrechten. Na beide geslaagde controles maakt **publish-catalog** op een beschermde SemVer-tag de catalogusrelease via GitLabs standaardveld `release:`. De publicatie controleert ook of de commit op `main` voorkomt.

De openbare broncode staat in [woozer/ci-pipelines](https://github.com/woozer/ci-pipelines). De lokale catalogus is beschikbaar na [installatie](https://github.com/woozer/ci-components/blob/main/installation.md).

De scannerjobs leveren naast volledige artifacts ook samenvattingen: Dependency-Check in de open MR, Sonar na analyse van main bij de commit en de bijbehorende gemergede MR. JUnit blijft beschikbaar onder **Tests** en in het MR-testoverzicht. Zie [rapportage en editiegrenzen](https://github.com/woozer/ci-components/blob/main/docs/scanners.md).
