# Fontes dos dados de Franca/SP

Gerado por `python -m scripts.fetch_franca_data`. Não editar à mão:
reexecute o script para atualizar os dados e a data de coleta.

Coletado em: 2026-10-01 20:17:07 (UTC)

| Camada | Provedor | Dataset | Licença |
| --- | --- | --- | --- |
| Limite municipal | IBGE | API de Malhas (qualidade máxima, GeoJSON) | CC-BY-SA 4.0 / uso público |
| Demografia | IBGE | Painel de Cidades (Franca/SP) | CC-BY-SA 4.0 |
| Hidrografia | OpenStreetMap | `waterway` stream/river/canal/ditch | ODbL |
| Sistema viario | OpenStreetMap | `highway` primary/secondary/trunk/tertiary | ODbL |
| Edificações | OpenStreetMap | `building` | ODbL |
| Cobertura do solo | OpenStreetMap | `landuse`, `natural`, `leisure` | ODbL |
| Equipamentos públicos | OpenStreetMap | `amenity` hospital/clinic/school | ODbL |
| Relevo | AWS Terrain Tiles | Terrarium sobre SRTM | CC-BY / uso público |
| Pontos vulneráveis | Prefeitura de Franca | Plano de Contingência de Defesa Civil | Documento público municipal |

## Contagens

- **Vertices do limite**: 779 vertices
- **Cursos d'agua**: 81 ways
- **Vias**: 1412 ways
- **Edificacoes**: 1390 ways
- **Cobertura do solo**: 493 polygons
- **Equipamentos publicos**: 131 elements
- **Celulas do DEM**: 256x288 cells
- **Pontos vulneraveis**: 5/5 resolvidos
- **Area do municipio**: 605,679 km2 (IBGE Malhas)
- **Area modelada**: 32,4% do municipio (janela URBAN_BBOX)

## Relevo

- Zoom 14, 49/49 tiles obtidos
- Altitude mínima 739.1 m, máxima 1060.1 m
- Resolução da grade publicada 46.4 m

## Pontos vulneráveis

As coordenadas são geolocalizadas no nível da via (OSM) a partir do nome
citado no plano municipal. `severity` é qualitativa e vem do documento;
o texto em `evidence` é a transcrição da fonte.

## Limitações conhecidas

As regiões do twin são **sub-bacias hidrográficas**, não bairros: Franca
não tem divisão territorial oficial publicada pelo IBGE.

**O modelo cobre 32,4% da área do município.** O limite do IBGE
tem 605,679 km², mas o DEM e todas as camadas derivadas são recortados pela
janela urbana em `URBAN_BBOX`. As sub-bacias são, portanto, as sub-bacias
que caem nessa janela, não a partição territorial do município.

- A população é rateada pela densidade real de edificações (OSM) e cada
  região carrega `population_is_estimated: true`. A soma fecha com o total
  municipal por construção, o que pressupõe que toda a população do
  município está dentro da janela modelada (32,4% da área).
  A periferia não é representada: ler as sub-bacias como cobertura do
  município inteiro superestima a densidade em todo o território.
- A vulnerabilidade social é um proxy por densidade de tecido urbano,
  não renda por setor censitário, que não está disponível aqui.
- A janela do DEM é um retângulo e o município não é: os cantos dela
  caem fora de Franca. As sub-bacias afetadas não são recortadas, porque
  uma bacia é unidade hidrológica e cortá-la por linha administrativa
  distorceria a partição. Elas carregam `within_municipality: false`.
- A impermeabilidade usa comprimento de rua por km2 como aproximação de
  área selada, porque a cobertura de edificações do OSM é esparsa.
- `landuse_coverage` informa quanto da região o OSM mapeia; os índices de
  vegetação e área construída leem só o que está mapeado.
- As unidades oficiais de risco potencial de erosão (DWG) não são
  georreferenciadas aqui: nenhum ponto de erosão é publicado.
- As fontes divergem no nome da terceira Colina, então o relevo não é
  rotulado.
- Dados externos não são chamados em runtime; a API lê apenas estes
  fixtures versionados.

## Referências

- IBGE Cidades Franca/SP: https://servicodados.ibge.gov.br/cidades-e-estados/sp/franca.html
- IBGE Malhas município 3516200: https://servicodados.ibge.gov.br/api/v3/malhas/municipios/3516200
- AWS Terrain Tiles: https://registry.opendata.aws/terrain-tiles/
- Plano de Contingência de Defesa Civil: https://www3.franca.sp.gov.br/pdf/20260316140411_69b8380b3cf8d_PLANO_DE_CONTING_NCIA_DE_DEFESA_CIVIL_-_PER_ODOS_CHUVOSOS_.pdf
