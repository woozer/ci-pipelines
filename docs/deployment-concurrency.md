# Deployment zonder childpipeline

Onderzoek van 11 september 2026 op GitLab CE 19.3.1. Dit document beschrijft mogelijkheden en gemeten gedrag. Het wijzigt de huidige deliverystrategie van de applicatie niet.

## Conclusie

Gewone jobs kunnen een reeks van deployment en tests na elkaar uitvoeren met de resourcegroepmodus `oldest_first`. GitLab Support beschrijft dit expliciet als alternatief voor childpipelines. De eerdere beoordeling dat resourcegroepen alleen losse jobs beschermen, was onvolledig: de planning houdt ook rekening met toekomstige jobs in oudere pipelines.

Het gedrag is echter niet gelijk aan onze huidige aanpak. Een herhaling van een oude deployment kan een nieuwere pipeline onderbreken tussen deployment en verificatie. Dat hebben we lokaal gereproduceerd. Het opnieuw starten van oude jobs en later activeren van releasejobs moeten daarom apart worden beoordeeld.

Voor onze gedeelde dev-omgeving blijft een childpipeline de eenvoudigste bewezen aanpak die aparte tool-images, een lock over de hele delivery en het herhalen van de volledige deployment-/testreeks combineert. Een pipeline met alleen gewone jobs is mogelijk, maar vraagt een andere afweging in het gebruik.

## Het ondersteunde patroon met gewone jobs

GitLab Support beschrijft een begin- en eindjob met dezelfde `resource_group`, ingesteld op `process_mode: oldest_first`. De eindjob moet afhankelijk zijn van al het beschermde werk; de tussenliggende jobs moeten afhankelijk zijn van de beginjob. Je kunt dezelfde resourcegroep ook aan iedere Helm- en integratietestjob toekennen. Dan worden die jobs ook binnen één pipeline na elkaar uitgevoerd.

De procesmodus is een instelling van het project en de resourcegroep via de GitLab API. Het is geen `process_mode`-veld in `.gitlab-ci.yml`. Configureer de modus voordat je op de volgorde vertrouwt. GitLab heeft ook een projectstandaard voor nieuwe resourcegroepen; bestaande groepen moet je apart controleren. Wijzig niet stilzwijgend alle groepen als alleen dev-delivery dit gedrag nodig heeft.

`oldest_first` houdt rekening met jobs in de statussen `created`, `scheduled` en `waiting_for_resource`. Daardoor kan een toekomstige verificatiejob in pipeline A de deployment van pipeline B laten wachten. `needs` en stages blijven de volgorde binnen iedere pipeline bepalen. Controleer voorwaardelijke jobs, handmatige stappen, fouten, overgeslagen jobs en herhalingen. Een geblokkeerde toekomstige job kan ook nieuwere deliveries ophouden.

Bronnen: [GitLab Support over gelijktijdige pipelines](https://support.gitlab.com/hc/en-us/articles/21727269790620-Achieve-Pipeline-level-concurrency-with-resource-group-CI-CD-keyword), [resourcegroepmodi](https://docs.gitlab.com/ci/resource_groups/#process-modes) en [Projects API](https://docs.gitlab.com/api/projects/). Ook de geïnstalleerde planningsimplementatie `Ci::ResourceGroup#upcoming_processables` is bekeken.

## Lokaal experiment

Het gearchiveerde project [CI ordering lab](http://localhost:8929/root/ci-ordering-lab) gebruikt jobs die hun pipeline-ID tonen en wachten. Ze deployen niets en wijzigen de applicatie niet. De volgorde is `deploy → between → verify`; `deploy` en `verify` delen een resourcegroep met `oldest_first`. De middelste job simuleert tijd tussen deployment en verificatie.

**Normale gelijktijdige pipelines:** [128](http://localhost:8929/root/ci-ordering-lab/-/pipelines/128) en [129](http://localhost:8929/root/ci-ordering-lab/-/pipelines/129) verliepen zo:

```text
128: deploy → between → verify
129: deploy → between → verify
```

**Herhaling van een oude job:** terwijl pipeline 130 bezig was met deployen, is de al afgeronde deployment van pipeline 128 opnieuw gestart. Alle jobs slaagden, maar de volgorde was:

| Gebeurtenis | Bewijs | Tijd in UTC |
|---|---|---|
| Pipeline 130 rondt deployment af | [Job 368](http://localhost:8929/root/ci-ordering-lab/-/jobs/368) | 13:13:14.486 |
| Herhaling van de deployment van pipeline 128 start | [Job 371](http://localhost:8929/root/ci-ordering-lab/-/jobs/371) | 13:13:32.249 |
| De oude deployment is opnieuw uitgevoerd | Job 371 | 13:13:55.898 |
| Pipeline 130 begint met verificatie | [Job 370](http://localhost:8929/root/ci-ordering-lab/-/jobs/370) | 13:13:57.989 |

Dit toont aan dat een oudere deployment opnieuw kan draaien tussen een nieuwere deployment en de bijbehorende test. In een gedeelde omgeving kan de test daardoor de oudere applicatie controleren. Het herhalen van de deployment startte de eerder geslaagde vervolgtests niet automatisch opnieuw.

De eerste twee testpipelines, 126 en 127, faalden bij het ophalen van de runner-helper, voordat experimentjobs draaiden. Na het instellen van de bestaande leescredentials leverden pipelines 128–130 het bovenstaande bewijs.

Het experiment testte herhalingen rechtstreeks. De zorg over later geactiveerde handmatige releasejobs in een oudere pipeline is afgeleid van dezelfde planningsregel op pipeline-ID. Dat is niet als afzonderlijk release-experiment uitgevoerd.

## Alternatieven en afwegingen

| Aanpak | Bescherming | Gevolg voor onze sample |
|---|---|---|
| Huidige childpipeline met `resource_group` en `strategy: mirror` | De trigger houdt de dev-lock vast totdat alle Helm- en integratiejobs klaar zijn | Aparte images en één volledige deliveryherhaling blijven mogelijk; GitLab toont de child rechts |
| Gewone jobs met `oldest_first` | Normaal verlopende pipelines draaien na elkaar; oude herhalingen kunnen een nieuwere reeks onderbreken | Vereist afspraken en handhaving voor herstarten en releases; is niet gelijk aan het huidige gedrag |
| Eén gewone deliveryjob met lock | Beschermt de volledige deployment-/testbewerking, ook bij herhaling | Aparte CI-jobs worden één job; vereist een gecombineerde tool-image of acceptatietests als Kubernetes Jobs |
| Aparte omgeving per pipeline | Andere pipelines deployen elders en vervangen de applicatie onder test niet | Behoudt aparte jobs/images; vereist routing, resourcelimieten, credentials en opruimen |

### Eén deliveryjob met Helm-hooks

Helm kan Kubernetes Job-hooks uitvoeren na installatie of upgrade. Als wachten op gereedheid is ingeschakeld, start de post-install-hook nadat de resources gereed zijn. Job-hooks moeten afronden voordat Helm klaar is. De tests kunnen in het cluster een eigen browserimage gebruiken, terwijl de CI-job alleen Helm gebruikt. Eén CI-resourcegroep kan dan de volledige bewerking beschermen.

Voor onze twee deployables vereist dit een gecombineerde release, bijvoorbeeld een umbrella chart, of één job die beide charts deployt en daarna acceptatietests uitvoert. De bestaande Cucumber-/Playwright-tests hebben dan een testimage met de juiste versie nodig, plus een manier om rapporten naar GitLab terug te sturen. Helm-hookresources vereisen ook een opruimbeleid. Dit is ondersteund Helm-gedrag, maar een grotere wijziging dan alleen de YAML anders indelen.

`helm test` voert testhooks expliciet uit. Dat valt niet automatisch onder een eerder geslaagde `helm upgrade --rollback-on-failure`. Verificatie via post-install-/post-upgrade-hooks en een apart `helm test`-commando hebben verschillend rollbackgedrag. Zie [Helm-hooks](https://helm.sh/docs/topics/charts_hooks/) en [Helm-charttests](https://helm.sh/docs/topics/chart_tests/).

### Gescheiden omgevingen

GitLabs dynamische omgevingen en review apps zijn een gangbaar alternatief. Gebruik voor gelijktijdige pipelinetests een omgeving en releasenaam/namespace die uniek zijn per pipeline. Alleen scheiden per branch is onvoldoende, omdat twee pipelines van dezelfde branch kunnen overlappen. Backend, UI en test-URL's moeten naar dezelfde gescheiden omgeving wijzen. Een GitLab-omgevingsvermelding maakt op zichzelf geen Kubernetes-resources aan en isoleert die niet. Zie [review apps](https://docs.gitlab.com/ci/review_apps/).

Dit past bij gelijktijdige ontwikkeling, maar verandert de vaste adressen `localhost:8080` en `localhost:8090` en vereist routing en opruimen. Als de applicatie later gegevens bewaart, moet ook gedeelde externe testdata worden gescheiden.

## Mogelijke werkwijze met nieuwe deliverypipelines

Bij gewone jobs met `oldest_first` kan iedere deliverypoging een nieuwe pipeline worden, in plaats van muterende jobs in oude pipelines te herhalen:

- Een main-pipeline bouwt, publiceert, deployt en verifieert met gewone jobs.
- De handmatige releaseknop kan een protected tag blijven reserveren. Een GitLab-tagpipeline bouwt en levert die release vervolgens met een eigen pipeline-ID. Dit is een aparte hoofdpipeline, geen childpipeline. Zie [GitLab-releasevoorbeelden](https://docs.gitlab.com/user/project/releases/release_cicd_examples/).
- Een herdeployment start een nieuwe pipeline voor alleen deployment, met bestaande onveranderlijke artifacts en het gekozen profiel. Bepaal eerst hoe artifacts en de juiste testbroncode worden geselecteerd voordat de huidige verwijzingen naar parentartifacts worden vervangen.

Dit verandert de gebruikershandelingen, maar voorkomt op zichzelf niet dat iemand een oude job herhaalt. Bescherming tegen verouderde deployments kan delen van het beleid afdwingen, maar vormt geen lock over deployment én tests. Een afspraak alleen biedt niet dezelfde bescherming. Zie [veilige deployments](https://docs.gitlab.com/ci/environments/deployment_safety/).

Cluster- en profielkeuzes kunnen GitLab-jobinputs blijven, met uitgestelde standaarduitvoering en dotenv-outputs voor gewone jobs. Daarvoor is op zichzelf geen childpipeline nodig. Dotenv-waarden die tijdens een job ontstaan, kunnen via `rules` geen nieuwe jobs selecteren. Gebruik een resourcegroepsleutel die bekend is bij het aanmaken van de pipeline. Zie [dotenv-variabelen](https://docs.gitlab.com/ci/variables/dotenv_variables/).

De ontwerpkeuze is dus welke eis kan veranderen: de gedeelde omgeving, aparte CI-jobs/tool-images of de huidige werkwijze voor herhalingen en releases. Er wordt geen eigen lockdienst of vervolgengine voorgesteld.
