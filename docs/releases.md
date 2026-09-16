# Gedeelde releasestrategie

Applicaties nemen het [pipelineformulier](../config/pipeline-inputs.yml) en [java-service.yml](../templates/java-service.yml) rechtstreeks op. Ze vullen `maven-project` in en geven de gekozen cluster-, gebruikers- en modusinstellingen door. De openbare ingang bepaalt de gewone pipeline en start afzonderlijke interne configuraties voor deployment en release. Build- en publicatiejobs worden gedeeld; de applicatie kiest geen interne uitvoeringsvariant. De bibliotheek beheert jobs, scripts, releaseknop, controles en dev-deployment. Applicaties hoeven geen releasepipeline te kopiëren of onderhouden.

Applicatienaam en namespace zijn standaard gelijk aan de GitLab-projectnaam; het standaardchartpad is `helm/<project-name>`. Helm laadt eerst `environment/cluster/<cluster>.yaml` en daarna `environment/user/<user-config>.yaml`. De centrale configuratie kiest clustercredentials, dev-URL's en HTTP-toegang tot de registry. Generieke componenten houden veilige protocoldefaults. Pas lokale infrastructuurinstellingen centraal aan. Neem optionele inputs alleen op als dat nodig is; deze demo schakelt de aparte UI in met `ui-directory: ui`.

De strategie ondersteunt een Maven-reactor met meerdere modules, één Java-deployable en een optionele aparte Angular-UI. Libraries en tests worden vanuit de root-POM gebouwd. Beide deployables delen één repositorytag en releaseversie. Voor meer Java-deployables zijn expliciete extra image-, chart- en deploymentjobs nodig, met eigen namen en outputs. Automatische verdeling over een willekeurig aantal deployables is niet geïmplementeerd.

De Java-strategie combineert onafhankelijke Maven-, Jib-, Helm- en releasecomponenten. Andere technologiestacks kunnen dezelfde releasecomponenten met hun eigen buildmodules gebruiken. Organisatie-URL's en images voor taken staan in de [organisatie-instellingen](https://github.com/woozer/ci-components/blob/main/config/organization.yml); toegangsgegevens staan in GitLab-variabelen.

## Een release starten en publiceren

Voor dagelijks gebruik zijn er [drie handelingen](../README.md#dagelijks-gebruik). Na een volledige, geslaagde pipeline op protected main reserveert **start-release** een versie en tag. De standaard `version: auto` kiest de volgende patch binnen `release-line`. De standaardreeks is `0.1`: eerst `0.1.0`, daarna `0.1.1`, enzovoort. Een handmatige versie moet binnen de ingestelde reeks vallen. De beperkte modi `validate` en `publish` geven geen toegang tot releasepublicatie.

**release-delivery** start `Release — <version>`. Deze pipeline bouwt, test en publiceert de gereserveerde versie, deployt die naar dev en voert API-/browsertests uit. De laatste job, **publish-release**, maakt de daadwerkelijke GitLab Release aan zodra alle verplichte validatie slaagt. Alleen een tag reserveren maakt nog geen releasevermelding aan. Afnemers die een oudere bibliotheekversie gebruiken, behouden de oude jobnamen totdat zij upgraden.

Er is geen aparte goedkeuring van de tag. Met **start-release** besluit je de release te starten; de codebeoordeling vindt vóór de merge plaats. De lokale demo heeft één gebruiker, die ook de MR merget. Vereis in de echte organisatie beoordeling door een tweede persoon vóór een merge naar een protected branch. Een handmatige knop alleen dwingt het vierogenprincipe niet af.

Een release levert onveranderlijke artifacts op. Die mogen naar dev worden gedeployed. Een toekomstige productiedeployment via Argo CD moet de bestaande image-digest en chartversie van de release gebruiken en mag de applicatie niet opnieuw bouwen. Productiedeployment via Argo CD valt buiten deze lokale demo.

## Release-artifactlinks

**publish-release** gebruikt de ondersteunde [GitLab Releases API](https://docs.gitlab.com/api/releases/#create-a-release) om in één verzoek toelichting en `assets.links` aan te maken. Per deployable zijn er links naar het image- en Helm-manifest. Daarnaast zijn er links naar de Maven-packagelijst en de validatiepipeline. De toelichting bevat de exacte image-digests en OCI-chartreferenties voor deployment.

GitLab-artifactlinks moeten HTTP(S)- of FTP-URL's zijn. Docker-pullreferenties en `oci://`-referenties zijn geen klikbare release-artifactlinks. In deze Artifactory-demo levert `ARTIFACTORY_PUBLIC_URL` het centrale browseradres. Manifestlinks verwijzen naar de gereserveerde versiemap in de repository die overschrijven weigert. Het zijn verwijzingen naar registry-artifacts, geen downloadbare archieven van Docker-images. De Maven-link opent de packagelijst van het project, niet één JAR. Registry-authenticatie blijft gelden; de links bevatten geen toegangsgegevens. Zie [GitLabs release-artifactvelden](https://docs.gitlab.com/user/project/releases/release_fields/#release-assets).

De optionele input `artifact-base-url` van de losse module accepteert een publieke Artifactory-root onder `/artifactory`. Zonder deze input verwijzen de links naar HTTPS OCI Distribution-manifestendpoints, op basis van image-digest en chartversie. Sommige registries vereisen authenticatie en een OCI-`Accept`-header voor chartmanifests. De Artifactory-instelling vermijdt die vereiste browserheader. Afnemers kunnen de input weglaten; de demo vult hem centraal in.

De links wijzen naar bestaande opslag en maken geen extra artifactkopie. Serverrechten beschermen tegen wijziging; een GitLab Release-vermelding doet dat op zichzelf niet. Dit geldt voor nieuwe releases en wijzigt geen bestaande releasevermeldingen.

## Versies en herhaalde pogingen

| Build | Versie |
|---|---|
| Zelfstandig `./mvnw verify` | Standaard `1.0.0-SNAPSHOT` |
| Ontwikkelpipeline | `0.0.0-dev.<pipeline-number>.g<commit>` |
| Officiële release | `release-line: "2.3"` levert `2.3.0`, `2.3.1`, enzovoort; Git-tag `v<version>` |

Maven, de imagetag en de Helm-chart gebruiken dezelfde gekozen versie. Elke nieuwe ontwikkelpipeline krijgt een nieuw nummer. Een releasenummer wordt nooit hergebruikt voor een andere commit of image. Onder de reserveringslock leest de automatische versiekeuze de remote `vX.Y.Z`-tags, gesorteerd op versie. Alleen tags binnen de ingestelde `release-line` tellen mee, ook die van mislukte releases. Tags uit andere reeksen en prereleasetags worden genegeerd. Als tags niet kunnen worden opgehaald, wordt publicatie geblokkeerd.

Major en minor leg je vast in de configuratie van het afnemende project, als input van de bestaande `java-service.yml`-include:

```yaml
inputs:
  # Other required inputs stay in the same include.
  release-line: "2.3"
```

De losse `release-reserve`-module ondersteunt dezelfde input. Laat hem weg zolang de standaard `0.1` passend is. Na een wijziging naar `2.4` of `3.0` begint de patch op nul, tenzij in die reeks al tags zijn gereserveerd. De wijziging gaat via een merge request naar de protected branch. De releasejob schrijft geen versiecommit terug. Ook een handmatig ingevoerd releasenummer moet binnen de beoordeelde reeks passen; daarmee kun je bijvoorbeeld een patch overslaan, maar geen major- of minorwijziging buiten het MR-proces om doen.

[Semantic Versioning](https://semver.org/) beschrijft de betekenis: major voor brekende API-wijzigingen, minor voor achterwaarts compatibele functionaliteit en patch voor achterwaarts compatibele foutcorrecties. Het team beoordeelt die impact in de merge request. De instelling `release-line` en de automatische patchverhoging zijn organisatiebeleid, geen ingebouwde GitLab-versiestrategie.

Maven gebruikt `${revision}` en de standaard Flatten Maven Plugin. CI geeft de versie door via `MAVEN_ARGS`; een releasecommit of releasebranch is niet nodig. Buiten CI bouwt en test `./mvnw -Drevision=1.2.3 verify` die versie zonder iets te publiceren. Zie [Maven CI Friendly Versions](https://maven.apache.org/guides/mini/guide-maven-ci-friendly.html).

De reserveringsjob maakt de Git-tag atomair aan op de exacte commit van de gekozen main-pipeline, ook als main intussen verder is. De tag reserveert het nummer permanent. Als de release mislukt, blijft de tag bestaan en wordt het nummer niet opnieuw gebruikt. Een bestaande image blokkeert een volgende releasebuild met dezelfde versie. Opnieuw deployen met de al gepubliceerde digest blijft mogelijk.

`release-reserve` heeft alleen Git-toegang nodig: de job kiest de versie en reserveert de tag. `release-check` controleert Artifactory één keer, vóór de releasebuild. Een onbereikbare registry of bestaande image/chart stopt de childpipeline; de tag blijft gereserveerd. Alleen `release-check` heeft daarom registry-credentials en artifactpaden als input nodig.

## Waar het gedrag is vastgelegd

| Bestand | Verantwoordelijkheid |
|---|---|
| [organization.yml](https://github.com/woozer/ci-components/blob/main/config/organization.yml) | Gedeelde serveradressen en images voor taken |
| [java-service.yml](../templates/java-service.yml) | Openbare ingang: gewone CI, profielkeuze, releaseknop en locks rond de childpipelines |
| [java-build.yml](../internal/java-build.yml) | Gedeelde build-, test-, scan- en publicatiejobs voor gewone CI en releases |
| [java-deploy.yml](../internal/java-deploy.yml) | Bestaande artifacts deployen en API-/browsertests uitvoeren |
| [java-release.yml](../internal/java-release.yml) | Gereserveerde versie controleren, bouwen, deployen, testen en als release vastleggen |
| [deployment-select.yml](https://github.com/woozer/ci-components/blob/main/templates/deployment-select.yml) | Cluster-/gebruikerswaarden kiezen en deploymentconfiguratie vastleggen |
| [release-reserve.yml](https://github.com/woozer/ci-components/blob/main/templates/release-reserve.yml) | Versie kiezen, Git-tag reserveren en versie/commit publiceren als inputs voor vervolgstappen |
| [release-check.yml](https://github.com/woozer/ci-components/blob/main/templates/release-check.yml) | Tag, commit en bestaande artifacts controleren vóór de releasebuild |
| [gitlab-release.yml](https://github.com/woozer/ci-components/blob/main/templates/gitlab-release.yml) | Geteste artifacts vastleggen als GitLab Release |
| [shared/release.yml](https://github.com/woozer/ci-components/blob/main/shared/release.yml) | Gedeelde validatiefuncties voor deze componenten |

De reserveringsjob schrijft een klein configuratieartifact voor de childpipeline. De centrale template en applicatie-instellingen liggen vast bij het aanmaken van de parentpipeline. De gekozen versie, exacte commit en geslaagde deploymentkeuzes worden tijdens de uitvoering ingevuld. Jobimplementaties blijven in de bibliotheek. Zo gebruikt een latere herhaling dezelfde oorspronkelijke inputs en bibliotheekversie.

## Afdwingen in GitLab en Artifactory

- Bescherm `main`: sta merges via MR's toe en weiger directe pushes en force-pushes, ook voor CI-accounts.
- Bescherm `v*`: alleen de release-deploy-key mag releasetags aanmaken. Tagpipelines publiceren niet; de protected branchpipeline beheert publicatie.
- Beperk releasecredentials tot protected refs en omgevingen onder `release/*`. Beperk de Git-deploy-key tot `release/reserve`. Gebruik getypeerde jobinputs en verbied willekeurige overrides van pipelinevariabelen.
- Publiceer images en OCI-charts naar `docker-releases-local` met een apart account met Read, Deploy en Annotate, zonder Delete/Overwrite, Manage of beheerdersrechten. Annotate laat Artifactory OCI-mediatype-eigenschappen vastleggen. Zonder dat recht kan Helm-publicatie falen door een onjuist manifest-Content-Type. Het recht staat overschrijven van artifacts niet toe. De ontwikkelpublisher heeft geen schrijftoegang tot deze repository.
- Schakel dubbele Maven-publicatie uit in de package-instellingen van de namespace. Elke pipeline krijgt een unieke ontwikkelversie; officiële versies worden met Git-tags gereserveerd.
- Voer reserveringsjobs na elkaar uit. Houd de delivery-childpipeline tot en met de laatste dev-test onder dezelfde dev-lock als gewone ontwikkeldeployments. Registry-rechten blijven nodig naast pipelinecontroles.

GitLab- en Artifactory-beheerders kunnen rechten aanpassen; CI mag hun credentials niet gebruiken. Protected tags regelen wie tags mag wijzigen, maar niet bij welke branch een commit hoort. Daarom controleren de releasecomponenten ook branchbescherming en commitafkomst. Zie [GitLab-tags](https://docs.gitlab.com/user/project/protected_tags/), [resourcegroepen](https://docs.gitlab.com/ci/resource_groups/) en [Artifactory-rechten](https://docs.jfrog.com/administration/docs/permissions).

Deze componenten zijn gedeeld, maar het opnemen van YAML richt geen serverrechten in. De lokale inrichting gebeurt met `infra/gitlab-runner/configure-releases.py`, buiten de applicatie. Richt overeenkomstige rechten in voor elk afnemend project en elke releaserepository in de organisatie.

De lokale testomgeving met gratis edities bewaart Maven-packages in GitLab en images/charts in Artifactory JCR. Testrapporten blijven in GitLab. JCR ondersteunt geen eigen Maven-repositories; daarvoor is een geschikte Artifactory-editie nodig. Zie [JFrog-edities](https://docs.jfrog.com/artifactory/docs/jfrog-container-registry).

## Repositories met de optionele UI

Met `ui-directory` omvat een gereserveerde release beide deployables met dezelfde versie. De afzonderlijke jobs `check-release` en `check-ui-release` weigeren bestaande image-/chartlocaties vóór het bouwen. Beide testsuites moeten vóór publicatie slagen. De backend gebruikt Jib; de UI gebruikt rootless BuildKit. Beide publiceren naar de onveranderlijke releaserepository, worden naar dev gedeployed en doorlopen HTTP-/browser-Cucumber-tests. Daarna legt `publish-release` beide image-digests en chartreferenties vast. Productie moet deze images promoveren zonder opnieuw te bouwen. De Helm-releases zijn afzonderlijk: een mislukte UI-deployment draait een eerder geslaagde backenddeployment niet automatisch terug. Houd API-wijzigingen daarom achterwaarts compatibel.
