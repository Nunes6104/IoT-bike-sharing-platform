(function () {
  "use strict";

  const Core = window.BikeDashboardCore;
  const translations = {
    en: {
      eyebrow: "Jersey City & Hoboken", title: "Bike-sharing operations", languageLabel: "Language",
      navAria: "Dashboard pages", summaryAria: "Period summary", stationMapAria: "Map of bike stations",
      profileSummaryAria: "Profile model summary", activeTripsSummaryAria: "Active trip summary",
      analyticsNav: "Analytics", mapNav: "Station map", profilesNav: "Station profiles", loading: "Loading dashboard data…",
      analyticsHeading: "Historical analytics",
      timezoneNote: "Stage 1 is a fixed offline baseline; Stage 2 metrics include MQTT events received so far and refresh as they arrive. Trip start times and bucket labels use source UTC−04:00; the end time is exclusive.",
      fromLabel: "From (UTC−04:00)", untilLabel: "Until, exclusive (UTC−04:00)",
      bucketLabel: "Trend interval", hourly: "Hourly", daily: "Daily", weekly: "Weekly (Monday start)",
      dateFormatHelp: "Select dates in 2024 and times in UTC−04:00. The end must be after the start; it is adjusted if the start moves past it.",
      emptyAnalytics: "No completed trips match this period.", completedTrips: "Completed trips",
      totalDurationHours: "Total duration (hours)", averageDurationMinutes: "Average duration (minutes)",
      estimatedFare: "Estimated fare (USD)", knownEnergy: "Known e-bike energy (kWh)",
      energyCoverage: "Energy coverage", unknownEnergyTrips: "E-bike trips with unknown energy",
      warningTrips: "Warning-bearing trips", tripTrendsHeading: "Completed trips by user type",
      energyFareHeading: "Energy and estimated fare", energyHeading: "Known e-bike energy (kWh)",
      fareHeading: "Estimated fare (USD)", durationHeading: "Trip duration",
      averageDurationHeading: "Average duration (minutes)", totalDurationHeading: "Total duration (hours)",
      timeOfDayHeading: "Trips by time of day", trendTableCaption: "Detailed trend values; unknown averages remain unknown.",
      bucketColumn: "Bucket start (UTC−04:00)", tripsColumn: "Trips", membersColumn: "Members",
      casualColumn: "Casual", avgColumn: "Avg duration (min)", totalColumn: "Total duration (h)",
      energyColumn: "Known energy (kWh)", unknownEnergyColumn: "Unknown energy trips",
      fareColumn: "Estimated fare (USD)", stationDemandHeading: "Station demand and observed availability",
      availabilityNote: "Empty/full shares use observed status updates, not elapsed time. Missing reports are not zero availability.",
      demandChartHeading: "Member/casual station departures and arrivals",
      emptyFullChartHeading: "Observed empty/full update shares (%)", stationTableCaption: "All reference stations; observed status counts are updates, not elapsed time.",
      stationColumn: "Station", memberDeparturesColumn: "Member departures",
      casualDeparturesColumn: "Casual departures", memberArrivalsColumn: "Member arrivals",
      casualArrivalsColumn: "Casual arrivals", updatesColumn: "Status updates",
      emptyColumn: "Empty updates", emptyShareColumn: "Empty update share (%)",
      fullColumn: "Full updates", fullShareColumn: "Full update share (%)", mapHeading: "Station availability map",
      mapScope: "Latest reports combine the fixed Stage 1 baseline with Stage 2 events received through MQTT, independent of analytics filters. The snapshot refreshes automatically; source times are historical replay times, not live bike positions.",
      activeTripsHeading: "Active trips in the Stage 2 stream",
      activeTripsNote: "Open trips reflect Stage 2 MQTT events received so far. A trip is open when its latest event is a start without a matching end. Times are historical replay times, not present-day riders; incomplete source records can remain open.",
      activeTripsEmpty: "No unmatched Stage 2 trip starts.",
      activeTripsCaption: "Open Stage 2 trips, ordered by most recently received start.",
      activeTripsCount: "Open trips", tripIdColumn: "Trip ID", tripStartedColumn: "Started (UTC−04:00)",
      tripStationColumn: "Start station", tripBikeColumn: "Bike type", tripUserColumn: "User type",
      classicBike: "Classic bike", electricBike: "Electric bike", memberUser: "Member", casualUser: "Casual",
      tileError: "Map tiles are unavailable. Station data and the station list remain available.",
      stationListHeading: "Stations", footerTimezone: "All displayed times use the source UTC−04:00 offset.",
      profilesHeading: "Station profiles and cluster evolution",
      profilesNote: "The Stage 1 model and baseline stay fixed; Stage 2 profiles use MQTT events received so far and refresh periodically. Daily profiles use source-local dates (UTC−04:00); missing status observations are not imputed.",
      profileFromLabel: "From (local date)", profileUntilLabel: "Until, exclusive (local date)",
      profileDateHelp: "Choose a 1–31 day range in the supplied dataset period. The end date is exclusive.",
      profilesEmpty: "No model or station profiles are available for this range.",
      clusterEvolutionHeading: "Station count by cluster and day",
      profileTableCaption: "Each row is a versioned station/day assignment with measured feature values.",
      dateColumn: "Local date", cityColumn: "City", clusterColumn: "Cluster",
      turnoverColumn: "Trips per dock", occupancyColumn: "Mean reported occupancy",
      memberShareColumn: "Member share", electricShareColumn: "E-bike share",
      distanceCoverageColumn: "Distance coverage", energyCoverageColumn: "Energy coverage",
      flagsHeading: "Explainable operational flags",
      flagsNote: "Flags are comparative or rule-based indicators, not rebalancing recommendations. They use observed data and explicit thresholds.",
      flagsEmpty: "No operational flags were triggered for this range.",
      flagsTableCaption: "Every flag includes its observed value and evaluation basis.",
      flagColumn: "Flag", severityColumn: "Severity", observedColumn: "Observed",
      thresholdColumn: "Threshold", basisColumn: "Basis", clusterLabel: "Cluster {id}",
      modelAlgorithm: "Model algorithm", clusterCount: "Clusters", modelTraining: "Training dates",
      profileCount: "Station/day profiles", flagCount: "Operational flags",
      loadingProfiles: "Loading station profiles…",
      lastProfiles: "Last successful profile fetch: {time}.",
      unknown: "Unknown", empty: "Empty (0 bikes)", full: "Full (0 docks)", reported: "Reported availability",
      bikesAvailable: "Bikes available", ebikesIncluded: "E-bikes (included in bikes available)",
      docksAvailable: "Docks available", disabledBikes: "Disabled bikes", disabledDocks: "Disabled docks",
      capacity: "Capacity", city: "City", lastReported: "Last reported", sequence: "Event sequence",
      installed: "Installed", renting: "Renting", returning: "Returning", warnings: "Validation warnings",
      yes: "Yes", no: "No", notMappable: "Not mappable (coordinates unavailable)",
      noWarnings: "No validation warnings",
      mapSnapshot: "Snapshot fetched {fetched}; latest committed event {event}.",
      chartTopStations: "Chart shows the {count} highest-demand stations; the table below retains all stations.",
      departuresMember: "Member departures", departuresCasual: "Casual departures",
      arrivalsMember: "Member arrivals", arrivalsCasual: "Casual arrivals",
      emptyShare: "Empty update share", fullShare: "Full update share", trips: "Trips",
      energy: "Energy (kWh)", fare: "Fare (USD)", averageDuration: "Average (min)",
      totalDuration: "Total (h)", night: "Night 00:00–06:00", morning: "Morning 06:00–12:00",
      afternoon: "Afternoon 12:00–18:00", evening: "Evening 18:00–24:00",
      initialLoading: "Loading data…", updated: "Updated {time}.",
      updatedWithTiming: "Updated {time}. Request: {requestMs} ms; render: {renderMs} ms.",
      updating: "Updating… Last successful data: {time}.", errorLoading: "Could not load data: {message}",
      authError: "Authentication failed. Sign in again to view dashboard data.",
      invalidFilter: "Choose dates in 2024; the start must precede the end and the range must not exceed 31 days.",
      requestError: "The service rejected the request: {message}",
      serviceError: "The service is temporarily unavailable. Retrying in {seconds} seconds.",
      networkError: "Network request failed. Retrying in {seconds} seconds.",
      requestFailed: "Request failed ({status}).", emptyStatus: "No station status report has been committed.",
      stationsObserved: "{count} stations have a committed status report.", chartImage: "{title} chart",
      oneStationObserved: "1 station has a committed status report.",
      noStations: "No reference stations are available.",
      zoomIn: "Zoom in", zoomOut: "Zoom out",
      chartNoValues: "No values to chart.", lastAnalytics: "Last successful analytics fetch: {time}.",
      loadingStation: "Loading latest station reports…", selectStation: "Select a station to see its details.",
      resultsRetained: "Showing the last successful data because this refresh failed."
    },
    "pt-PT": {
      eyebrow: "Jersey City e Hoboken", title: "Operações de bicicletas partilhadas", languageLabel: "Idioma",
      navAria: "Páginas do painel", summaryAria: "Resumo do período", stationMapAria: "Mapa das estações de bicicletas",
      profileSummaryAria: "Resumo do modelo de perfis",
      analyticsNav: "Análise", mapNav: "Mapa das estações", profilesNav: "Perfis das estações", loading: "A carregar dados do painel…",
      analyticsHeading: "Análise histórica",
      timezoneNote: "A Fase 1 é uma base offline fixa; as métricas da Fase 2 incluem os eventos MQTT recebidos até ao momento e atualizam à medida que chegam. As horas usam o fuso de origem UTC−04:00; a hora final é exclusiva.",
      fromLabel: "De (UTC−04:00)", untilLabel: "Até, exclusivo (UTC−04:00)",
      bucketLabel: "Intervalo da tendência", hourly: "Por hora", daily: "Por dia", weekly: "Por semana (início à segunda-feira)",
      dateFormatHelp: "Selecione datas em 2024 e horas em UTC−04:00. O fim deve ser posterior ao início; é ajustado se o início o ultrapassar.",
      emptyAnalytics: "Não existem viagens concluídas neste período.", completedTrips: "Viagens concluídas",
      totalDurationHours: "Duração total (horas)", averageDurationMinutes: "Duração média (minutos)",
      estimatedFare: "Tarifa estimada (USD)", knownEnergy: "Energia conhecida de bicicletas elétricas (kWh)",
      energyCoverage: "Cobertura energética", unknownEnergyTrips: "Viagens elétricas com energia desconhecida",
      warningTrips: "Viagens com avisos", tripTrendsHeading: "Viagens concluídas por tipo de utilizador",
      energyFareHeading: "Energia e tarifa estimada", energyHeading: "Energia conhecida de bicicletas elétricas (kWh)",
      fareHeading: "Tarifa estimada (USD)", durationHeading: "Duração das viagens",
      averageDurationHeading: "Duração média (minutos)", totalDurationHeading: "Duração total (horas)",
      timeOfDayHeading: "Viagens por período do dia", trendTableCaption: "Valores detalhados; as médias desconhecidas mantêm-se desconhecidas.",
      bucketColumn: "Início do intervalo (UTC−04:00)", tripsColumn: "Viagens", membersColumn: "Membros",
      casualColumn: "Ocasional", avgColumn: "Duração média (min)", totalColumn: "Duração total (h)",
      energyColumn: "Energia conhecida (kWh)", unknownEnergyColumn: "Viagens com energia desconhecida",
      fareColumn: "Tarifa estimada (USD)", stationDemandHeading: "Procura e disponibilidade observada das estações",
      availabilityNote: "As proporções de vazio/cheio usam atualizações de estado observadas, não tempo decorrido. Relatórios em falta não significam disponibilidade zero.",
      demandChartHeading: "Partidas e chegadas por tipo de utilizador",
      emptyFullChartHeading: "Proporções observadas de atualizações vazias/cheias (%)", stationTableCaption: "Todas as estações de referência; as contagens são atualizações, não tempo decorrido.",
      stationColumn: "Estação", memberDeparturesColumn: "Partidas de membros",
      casualDeparturesColumn: "Partidas ocasionais", memberArrivalsColumn: "Chegadas de membros",
      casualArrivalsColumn: "Chegadas ocasionais", updatesColumn: "Atualizações de estado",
      emptyColumn: "Atualizações vazias", emptyShareColumn: "Proporção de atualizações vazias (%)",
      fullColumn: "Atualizações cheias", fullShareColumn: "Proporção de atualizações cheias (%)",
      mapHeading: "Mapa de disponibilidade das estações",
      mapScope: "Os relatórios mais recentes combinam a base fixa da Fase 1 com eventos da Fase 2 recebidos por MQTT, independentemente dos filtros de análise. A consulta atualiza automaticamente; as horas são da reprodução histórica, não posições atuais das bicicletas.",
      activeTripsHeading: "Viagens ativas na sequência da Fase 2",
      activeTripsNote: "As viagens abertas refletem os eventos MQTT da Fase 2 recebidos até ao momento. Uma viagem está aberta quando o último evento é uma partida sem chegada correspondente. As horas são da reprodução histórica, não indicam ciclistas atuais; registos incompletos podem permanecer abertos.",
      activeTripsEmpty: "Não existem partidas da Fase 2 sem chegada correspondente.",
      activeTripsCaption: "Viagens abertas da Fase 2, ordenadas pela partida recebida mais recentemente.",
      activeTripsCount: "Viagens abertas", tripIdColumn: "ID da viagem", tripStartedColumn: "Partida (UTC−04:00)",
      tripStationColumn: "Estação de partida", tripBikeColumn: "Tipo de bicicleta", tripUserColumn: "Tipo de utilizador",
      classicBike: "Bicicleta clássica", electricBike: "Bicicleta elétrica", memberUser: "Membro", casualUser: "Ocasional",
      tileError: "Os mosaicos do mapa estão indisponíveis. Os dados e a lista de estações continuam disponíveis.",
      stationListHeading: "Estações", footerTimezone: "Todas as horas apresentadas usam o desvio de origem UTC−04:00.",
      profilesHeading: "Perfis das estações e evolução dos grupos",
      profilesNote: "O modelo e a base da Fase 1 permanecem fixos; os perfis da Fase 2 usam os eventos MQTT recebidos até ao momento e atualizam periodicamente. Os perfis diários usam datas locais de origem (UTC−04:00); observações em falta não são imputadas.",
      profileFromLabel: "De (data local)", profileUntilLabel: "Até, exclusivo (data local)",
      profileDateHelp: "Selecione um intervalo de 1–31 dias no período do conjunto de dados fornecido. A data final é exclusiva.",
      profilesEmpty: "Não existem modelos ou perfis de estação neste intervalo.",
      clusterEvolutionHeading: "Número de estações por grupo e dia",
      profileTableCaption: "Cada linha é uma atribuição versionada por estação/dia com valores de funcionalidades medidas.",
      dateColumn: "Data local", cityColumn: "Cidade", clusterColumn: "Grupo",
      turnoverColumn: "Viagens por doca", occupancyColumn: "Ocupação média observada",
      memberShareColumn: "Proporção de membros", electricShareColumn: "Proporção de bicicletas elétricas",
      distanceCoverageColumn: "Cobertura de distância", energyCoverageColumn: "Cobertura energética",
      flagsHeading: "Sinalizações operacionais explicáveis",
      flagsNote: "As sinalizações são indicadores comparativos ou baseados em regras, não recomendações de redistribuição. Usam dados observados e limites explícitos.",
      flagsEmpty: "Não foram acionadas sinalizações operacionais neste intervalo.",
      flagsTableCaption: "Cada sinalização inclui o valor observado e a respetiva base de avaliação.",
      flagColumn: "Sinalização", severityColumn: "Gravidade", observedColumn: "Observado",
      thresholdColumn: "Limite", basisColumn: "Base", clusterLabel: "Grupo {id}",
      modelAlgorithm: "Algoritmo do modelo", clusterCount: "Grupos", modelTraining: "Datas de treino",
      profileCount: "Perfis estação/dia", flagCount: "Sinalizações operacionais",
      loadingProfiles: "A carregar perfis das estações…",
      lastProfiles: "Última consulta bem-sucedida dos perfis: {time}.",
      unknown: "Desconhecido", empty: "Vazia (0 bicicletas)", full: "Cheia (0 docas)", reported: "Disponibilidade reportada",
      bikesAvailable: "Bicicletas disponíveis", ebikesIncluded: "Bicicletas elétricas (incluídas no total)",
      docksAvailable: "Docas disponíveis", disabledBikes: "Bicicletas indisponíveis", disabledDocks: "Docas indisponíveis",
      capacity: "Capacidade", city: "Cidade", lastReported: "Último relatório", sequence: "Sequência do evento",
      installed: "Instalada", renting: "Aluguer", returning: "Devoluções", warnings: "Avisos de validação",
      yes: "Sim", no: "Não", notMappable: "Sem localização no mapa (coordenadas indisponíveis)",
      noWarnings: "Sem avisos de validação",
      mapSnapshot: "Consulta obtida {fetched}; evento confirmado mais recente {event}.",
      chartTopStations: "O gráfico apresenta as {count} estações com maior procura; a tabela inclui todas as estações.",
      departuresMember: "Partidas de membros", departuresCasual: "Partidas ocasionais",
      arrivalsMember: "Chegadas de membros", arrivalsCasual: "Chegadas ocasionais",
      emptyShare: "Proporção de atualizações vazias", fullShare: "Proporção de atualizações cheias", trips: "Viagens",
      energy: "Energia (kWh)", fare: "Tarifa (USD)", averageDuration: "Média (min)",
      totalDuration: "Total (h)", night: "Noite 00:00–06:00", morning: "Manhã 06:00–12:00",
      afternoon: "Tarde 12:00–18:00", evening: "Fim de tarde/noite 18:00–24:00",
      initialLoading: "A carregar dados…", updated: "Atualizado às {time}.",
      updatedWithTiming: "Atualizado às {time}. Pedido: {requestMs} ms; apresentação: {renderMs} ms.",
      updating: "A atualizar… Últimos dados obtidos às {time}.", errorLoading: "Não foi possível carregar os dados: {message}",
      authError: "Falha de autenticação. Inicie sessão novamente para consultar o painel.",
      invalidFilter: "Selecione datas em 2024; o início deve anteceder o fim e o intervalo não pode exceder 31 dias.",
      requestError: "O serviço rejeitou o pedido: {message}",
      serviceError: "O serviço está temporariamente indisponível. Nova tentativa em {seconds} segundos.",
      networkError: "Falha de rede. Nova tentativa em {seconds} segundos.",
      requestFailed: "Pedido falhou ({status}).", emptyStatus: "Ainda não foi confirmado qualquer relatório de estado.",
      stationsObserved: "{count} estações têm um relatório de estado confirmado.", chartImage: "Gráfico: {title}",
      oneStationObserved: "1 estação tem um relatório de estado confirmado.",
      noStations: "Não existem estações de referência disponíveis.",
      zoomIn: "Aumentar zoom", zoomOut: "Diminuir zoom",
      chartNoValues: "Sem valores para apresentar.", lastAnalytics: "Última consulta de análise bem-sucedida: {time}.",
      loadingStation: "A carregar os relatórios mais recentes…", selectStation: "Selecione uma estação para ver os detalhes.",
      resultsRetained: "A apresentar os últimos dados bem-sucedidos porque esta atualização falhou."
    }
  };

  const $ = function (id) { return document.getElementById(id); };
  const state = {
    lang: readLanguage(),
    page: location.pathname.endsWith("/map") ? "map"
      : location.pathname.endsWith("/profiles") ? "profiles" : "analytics",
    analytics: null, snapshot: null, profiles: null,
    lastAnalyticsAt: null, lastSnapshotAt: null, lastProfilesAt: null,
    timer: null, filterTimer: null, request: null, generation: 0, retries: 0,
    connectionMessage: null, errorMessage: null, errorRetained: false,
    map: null, markerById: new Map(), selectedStationId: null, didFitMap: false,
    tileError: false
  };

  function readLanguage() {
    try { return localStorage.getItem("bike-dashboard-language") === "pt-PT" ? "pt-PT" : "en"; }
    catch (_) { return "en"; }
  }

  function t(key, values) {
    let value = translations[state.lang][key] || translations.en[key] || key;
    Object.keys(values || {}).forEach(function (name) { value = value.replace("{" + name + "}", values[name]); });
    return value;
  }

  function saveLanguage() {
    try { localStorage.setItem("bike-dashboard-language", state.lang); } catch (_) { /* Session-only preference is fine. */ }
  }

  function applyLanguage() {
    document.documentElement.lang = state.lang;
    document.title = t("title");
    $("language").value = state.lang;
    document.querySelectorAll("[data-i18n]").forEach(function (element) {
      const key = element.getAttribute("data-i18n");
      element.textContent = t(key);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach(function (element) {
      element.setAttribute("aria-label", t(element.getAttribute("data-i18n-aria")));
    });
    $("language").setAttribute("aria-label", t("languageLabel"));
    document.querySelectorAll("nav a").forEach(function (link) {
      link.setAttribute("aria-current", link.dataset.route === state.page ? "page" : "false");
    });
    if (state.analytics) renderAnalytics();
    if (state.snapshot) renderSnapshot();
    if (state.profiles) renderProfiles();
    if (state.lastAnalyticsAt) {
      $("last-analytics-update").textContent = t("lastAnalytics", {
        time: Core.formatTimestamp(state.lastAnalyticsAt)
      });
    }
    renderStatus();
    if (state.map) {
      const zoomIn = document.querySelector(".leaflet-control-zoom-in");
      const zoomOut = document.querySelector(".leaflet-control-zoom-out");
      if (zoomIn) {
        zoomIn.title = t("zoomIn");
        zoomIn.setAttribute("aria-label", t("zoomIn"));
      }
      if (zoomOut) {
        zoomOut.title = t("zoomOut");
        zoomOut.setAttribute("aria-label", t("zoomOut"));
      }
    }
  }

  function setPage(page, updateHistory) {
    const routes = { analytics: "/bike-sharing", map: "/bike-sharing/map", profiles: "/bike-sharing/profiles" };
    if (updateHistory) history.pushState({}, "", routes[page]);
    if (state.page === page && !$((page === "analytics" ? "analytics" : page) + "-page").hidden) return;
    state.page = page;
    state.generation += 1;
    clearTimeout(state.timer);
    if (state.request) state.request.abort();
    $("analytics-page").hidden = page !== "analytics";
    $("map-page").hidden = page !== "map";
    $("profiles-page").hidden = page !== "profiles";
    applyLanguage();
    if (page === "map" && state.map) setTimeout(function () { state.map.invalidateSize(); }, 0);
    pollNow();
  }

  function formatNumber(value, digits) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return t("unknown");
    return Number(value).toFixed(digits === undefined ? 0 : digits);
  }

  function createCard(label, value) {
    const card = document.createElement("div");
    card.className = "card";
    const title = document.createElement("span");
    title.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    card.append(title, strong);
    return card;
  }

  function addCells(target, values) {
    const row = document.createElement("tr");
    values.forEach(function (value) {
      const cell = document.createElement("td");
      cell.textContent = value === null || value === undefined ? t("unknown") : String(value);
      row.appendChild(cell);
    });
    target.appendChild(row);
  }

  function svgElement(name, attributes) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.keys(attributes || {}).forEach(function (key) { element.setAttribute(key, attributes[key]); });
    return element;
  }

  function renderBarChart(targetId, rows, series, options) {
    const target = $(targetId);
    target.replaceChildren();
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.className = "chart-empty";
      empty.textContent = t("chartNoValues");
      target.appendChild(empty);
      return;
    }
    const width = Math.max(520, rows.length * 52);
    const height = 265;
    const margin = { top: 16, right: 12, bottom: 62, left: 52 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const getValue = function (row, key) {
      if (row[key] === null || row[key] === undefined) return null;
      const value = Number(row[key]) / (options.divisor || 1);
      return Number.isFinite(value) && value >= 0 ? value : null;
    };
    const values = rows.map(function (row) { return series.map(function (item) { return getValue(row, item.key); }); });
    const maximum = Math.max(1, ...values.map(function (line) {
      return options.stacked
        ? line.reduce(function (sum, value) { return sum + (value || 0); }, 0)
        : Math.max.apply(null, line.map(function (value) { return value || 0; }));
    }));
    const svg = svgElement("svg", {
      viewBox: "0 0 " + width + " " + height, role: "img", focusable: "false",
      "aria-label": t("chartImage", { title: options.title })
    });
    for (let tick = 0; tick <= 4; tick += 1) {
      const y = margin.top + plotHeight - plotHeight * tick / 4;
      svg.appendChild(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: y, y2: y, stroke: "#dce5e8" }));
      const label = svgElement("text", { x: margin.left - 7, y: y + 4, "text-anchor": "end", fill: "#526670", "font-size": "11" });
      label.textContent = (maximum * tick / 4).toFixed(maximum < 10 ? 1 : 0);
      svg.appendChild(label);
    }
    const groupWidth = plotWidth / rows.length;
    const barWidth = Math.max(3, Math.min(34, groupWidth * (options.stacked ? .66 : .76) / series.length));
    rows.forEach(function (row, index) {
      let stackOffset = 0;
      series.forEach(function (item, seriesIndex) {
        const value = values[index][seriesIndex];
        if (value === null) return;
        const x = margin.left + groupWidth * index + groupWidth / 2
          - (options.stacked ? barWidth / 2 : (series.length * barWidth) / 2)
          + (options.stacked ? 0 : seriesIndex * barWidth);
        const barHeight = plotHeight * value / maximum;
        const y = margin.top + plotHeight - barHeight - stackOffset;
        const rect = svgElement("rect", {
          x: x, y: y, width: barWidth - 2, height: Math.max(1, barHeight),
          rx: "2", fill: item.color
        });
        const title = svgElement("title");
        title.textContent = (row.label || row.bucket || row.station_id) + " — "
          + (item.displayLabel || t(item.label)) + ": " + value;
        rect.appendChild(title);
        svg.appendChild(rect);
        if (options.stacked) stackOffset += barHeight;
      });
      const xLabel = svgElement("text", {
        x: margin.left + groupWidth * index + groupWidth / 2,
        y: height - margin.bottom + 13, fill: "#425964", "font-size": "10",
        "text-anchor": "end", transform: "rotate(-40 " +
          (margin.left + groupWidth * index + groupWidth / 2) + " " + (height - margin.bottom + 13) + ")"
      });
      xLabel.textContent = options.label ? options.label(row) : (row.bucket ? Core.formatBucket(row.bucket, options.bucket) : row.label || row.station_id);
      svg.appendChild(xLabel);
    });
    target.appendChild(svg);
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    series.forEach(function (item) {
      const entry = document.createElement("span");
      entry.style.marginRight = ".8rem";
      const swatch = document.createElement("i");
      swatch.setAttribute("aria-hidden", "true");
      swatch.style.cssText = "display:inline-block;width:.7rem;height:.7rem;margin-right:.3rem;background:" + item.color;
      entry.append(swatch, document.createTextNode(item.displayLabel || t(item.label)));
      legend.appendChild(entry);
    });
    target.appendChild(legend);
  }

  function renderAnalytics() {
    const data = state.analytics;
    if (!data) return;
    const summary = data.summary;
    $("summary").replaceChildren(
      createCard(t("completedTrips"), formatNumber(summary.completed_trips)),
      createCard(t("totalDurationHours"), formatNumber(summary.duration_seconds_total / 3600, 2)),
      createCard(t("averageDurationMinutes"), summary.duration_seconds_average === null
        ? t("unknown") : formatNumber(summary.duration_seconds_average / 60, 2)),
      createCard(t("estimatedFare"), "$" + formatNumber(summary.fare_usd_total, 2)),
      createCard(t("knownEnergy"), formatNumber(summary.energy_kwh_known_total, 3)),
      createCard(t("energyCoverage"), formatNumber(summary.energy_coverage_percent, 2) + "%"),
      createCard(t("unknownEnergyTrips"), formatNumber(summary.energy_unknown_trips)),
      createCard(t("warningTrips"), formatNumber(summary.warning_trips))
    );
    $("empty-analytics").hidden = summary.completed_trips !== 0;

    const trendRows = data.trends.map(function (point) { return Object.assign({ label: point.bucket }, point); });
    const stationRows = data.station_utilization;
    renderBarChart("trip-chart", trendRows, [
      { key: "member_trips", label: "membersColumn", color: "#087f9d" },
      { key: "casual_trips", label: "casualColumn", color: "#e18b28" }
    ], { title: t("tripTrendsHeading"), bucket: data.bucket, stacked: true });
    renderBarChart("energy-chart", trendRows, [
      { key: "energy_kwh_known", label: "energy", color: "#168a67" }
    ], { title: t("energyHeading"), bucket: data.bucket });
    renderBarChart("fare-chart", trendRows, [
      { key: "fare_usd", label: "fare", color: "#6d68b5" }
    ], { title: t("fareHeading"), bucket: data.bucket });
    renderBarChart("average-duration-chart", trendRows, [
      { key: "duration_seconds_average", label: "averageDuration", color: "#be6b82" }
    ], { title: t("averageDurationHeading"), bucket: data.bucket, divisor: 60 });
    renderBarChart("total-duration-chart", trendRows, [
      { key: "duration_seconds_total", label: "totalDuration", color: "#507dba" }
    ], { title: t("totalDurationHeading"), bucket: data.bucket, divisor: 3600 });

    const periodKey = { night: "night", morning: "morning", afternoon: "afternoon", evening: "evening" };
    const periodValues = $("period-values");
    periodValues.replaceChildren();
    data.time_of_day.forEach(function (item) {
      const entry = document.createElement("li");
      entry.textContent = t(periodKey[item.period] || item.period) + ": " + item.trips;
      periodValues.appendChild(entry);
    });
    renderBarChart("period-chart", data.time_of_day.map(function (item) {
      return { label: t(periodKey[item.period] || item.period), trips: item.trips };
    }), [{ key: "trips", label: "trips", color: "#087f9d" }],
    { title: t("timeOfDayHeading"), label: function (item) { return item.label; } });

    const topStations = stationRows.slice(0, 15);
    $("station-chart-note").textContent = t("chartTopStations", { count: topStations.length });
    renderBarChart("demand-chart", topStations.map(function (item) {
      return Object.assign({ label: item.station_id }, item);
    }), [
      { key: "departures_member", label: "departuresMember", color: "#087f9d" },
      { key: "departures_casual", label: "departuresCasual", color: "#e18b28" },
      { key: "arrivals_member", label: "arrivalsMember", color: "#168a67" },
      { key: "arrivals_casual", label: "arrivalsCasual", color: "#6d68b5" }
    ], { title: t("demandChartHeading"), label: function (item) { return item.station_id; } });
    renderBarChart("empty-full-chart", topStations.map(function (item) {
      return Object.assign({ label: item.station_id }, item, {
        empty_percent: item.empty_update_share === null ? null : item.empty_update_share * 100,
        full_percent: item.full_update_share === null ? null : item.full_update_share * 100
      });
    }), [
      { key: "empty_percent", label: "emptyShare", color: "#cf684d" },
      { key: "full_percent", label: "fullShare", color: "#5575a8" }
    ], { title: t("emptyFullChartHeading"), label: function (item) { return item.station_id; } });

    const trends = $("trends");
    trends.replaceChildren();
    data.trends.forEach(function (point) {
      addCells(trends, [
        Core.formatBucket(point.bucket, data.bucket), point.trips, point.member_trips, point.casual_trips,
        point.duration_seconds_average === null ? t("unknown") : formatNumber(point.duration_seconds_average / 60, 2),
        formatNumber(point.duration_seconds_total / 3600, 2), point.energy_kwh_known,
        point.energy_unknown_trips, "$" + formatNumber(point.fare_usd, 2)
      ]);
    });
    const stations = $("stations");
    stations.replaceChildren();
    stationRows.forEach(function (station) {
      addCells(stations, [
        station.station_name + " (" + station.station_id + ")", station.departures_member,
        station.departures_casual, station.arrivals_member, station.arrivals_casual,
        station.observed_status_updates, station.empty_updates,
        station.empty_update_share === null ? t("unknown") : formatNumber(station.empty_update_share * 100, 2) + "%",
        station.full_updates,
        station.full_update_share === null ? t("unknown") : formatNumber(station.full_update_share * 100, 2) + "%"
      ]);
    });
  }

  function renderProfiles() {
    const data = state.profiles;
    if (!data) return;
    const model = data.model;
    $("profiles-empty").hidden = Boolean(model && data.profiles.length);
    $("flags-empty").hidden = data.flags.length > 0;
    const summary = $("profile-summary");
    summary.replaceChildren();
    if (model) {
      summary.append(
        createCard(t("modelAlgorithm"), model.algorithm),
        createCard(t("clusterCount"), formatNumber(model.cluster_count)),
        createCard(t("modelTraining"), model.training_start + " – " + model.training_end + " (exclusive)"),
        createCard(t("profileCount"), formatNumber(data.profiles.length)),
        createCard(t("flagCount"), formatNumber(data.flags.length))
      );
    }

    const dates = Array.from(new Set(data.evolution.map(function (row) {
      return row.window_start;
    }))).sort();
    const clusterIds = Array.from(new Set(data.evolution.map(function (row) {
      return row.cluster_id;
    }))).sort(function (left, right) { return left - right; });
    const chartRows = dates.map(function (day) {
      const row = { label: day };
      clusterIds.forEach(function (clusterId) { row["cluster_" + clusterId] = 0; });
      data.evolution.filter(function (item) { return item.window_start === day; })
        .forEach(function (item) { row["cluster_" + item.cluster_id] = item.station_count; });
      return row;
    });
    const palette = ["#087f9d", "#e18b28", "#168a67", "#6d68b5", "#be6b82", "#507dba", "#9a7a38", "#5f7c67"];
    renderBarChart("cluster-chart", chartRows, clusterIds.map(function (clusterId, index) {
      return {
        key: "cluster_" + clusterId,
        label: "clusterLabel",
        displayLabel: t("clusterLabel", { id: clusterId }),
        color: palette[index % palette.length]
      };
    }), {
      title: t("clusterEvolutionHeading"),
      label: function (row) { return row.label; },
      stacked: true
    });

    const profileTable = $("profiles");
    profileTable.replaceChildren();
    data.profiles.forEach(function (profile) {
      const features = profile.features;
      addCells(profileTable, [
        profile.window_start,
        profile.station_id,
        profile.city,
        profile.cluster_id,
        formatNumber(features.trips_per_capacity, 3),
        features.mean_occupancy === null ? t("unknown") : formatNumber(features.mean_occupancy * 100, 1) + "%",
        features.member_share === null ? t("unknown") : formatNumber(features.member_share * 100, 1) + "%",
        features.electric_share === null ? t("unknown") : formatNumber(features.electric_share * 100, 1) + "%",
        features.distance_coverage === null ? t("unknown") : formatNumber(features.distance_coverage * 100, 1) + "%",
        features.energy_kwh === null ? t("unknown") : formatNumber(features.energy_kwh, 3),
        features.energy_coverage === null ? t("unknown") : formatNumber(features.energy_coverage * 100, 1) + "%"
      ]);
    });

    const flagTable = $("profile-flags");
    flagTable.replaceChildren();
    data.flags.forEach(function (flag) {
      addCells(flagTable, [
        flag.window_start,
        flag.station_id,
        flag.type,
        flag.severity,
        formatNumber(flag.observed, 3),
        formatNumber(flag.threshold, 3),
        flag.basis
      ]);
    });
  }

  function syncEndControls(adjustEnd) {
    const start = $("start");
    const end = $("end");
    if (!start.validity.valid) {
      end.disabled = true;
      return;
    }
    end.disabled = false;
    end.min = Core.minimumEnd(start.value);
    if (adjustEnd && end.value && end.value < end.min) end.value = end.min;
  }

  function parseFilters() {
    try {
      if (!$("start").validity.valid || !$("end").validity.valid || $("end").disabled) {
        throw new Error(t("invalidFilter"));
      }
      const start = Core.parseDateTime($("start").value.trim());
      const end = Core.parseDateTime($("end").value.trim());
      const duration = new Date(end).getTime() - new Date(start).getTime();
      if (duration <= 0 || duration > 31 * 24 * 60 * 60 * 1000) throw new Error(t("invalidFilter"));
      return { start: start, end: end, bucket: $("bucket").value };
    } catch (error) {
      throw new Error(error.message === t("invalidFilter") ? error.message : t("invalidFilter"));
    }
  }

  function paramsForAnalytics() {
    const filters = parseFilters();
    const params = new URLSearchParams({ start: filters.start, end: filters.end, bucket: filters.bucket });
    return "/api/analytics?" + params.toString();
  }

  function paramsForProfiles() {
    const startInput = $("profile-start");
    const endInput = $("profile-end");
    const start = startInput.value;
    const end = endInput.value;
    const dayCount = (Date.parse(end + "T00:00:00Z") - Date.parse(start + "T00:00:00Z"))
      / (24 * 60 * 60 * 1000);
    if (!startInput.validity.valid || !endInput.validity.valid
      || !Number.isInteger(dayCount) || dayCount < 1 || dayCount > 31) {
      throw new Error(t("invalidFilter"));
    }
    return "/api/ml/profiles?" + new URLSearchParams({ start: start, end: end }).toString();
  }

  function clearRequestTimer(controller, timeout) {
    clearTimeout(timeout);
    if (state.request === controller) state.request = null;
  }

  async function fetchJson(url, generation) {
    const controller = new AbortController();
    state.request = controller;
    const requestStartedAt = performance.now();
    let timedOut = false;
    const timeout = setTimeout(function () { timedOut = true; controller.abort(); }, 10000);
    try {
      const response = await fetch(url, {
        credentials: "same-origin", headers: { Accept: "application/json" }, signal: controller.signal
      });
      let payload;
      try { payload = await response.json(); }
      catch (_) {
        const error = new Error("The service returned an invalid JSON response.");
        error.status = response.status;
        throw error;
      }
      if (generation !== state.generation || controller.signal.aborted) return null;
      if (!response.ok) {
        const error = new Error(payload.error || t("requestFailed", { status: response.status }));
        error.status = response.status;
        throw error;
      }
      const validAnalytics = payload && typeof payload === "object"
        && Array.isArray(payload.trends)
        && Array.isArray(payload.time_of_day)
        && Array.isArray(payload.station_utilization)
        && payload.summary && typeof payload.summary === "object";
      const validSnapshot = payload && typeof payload === "object"
        && Array.isArray(payload.stations) && Array.isArray(payload.active_trips)
        && typeof payload.fetched_at === "string";
      const validProfiles = payload && typeof payload === "object"
        && (payload.model === null || typeof payload.model === "object")
        && Array.isArray(payload.profiles)
        && Array.isArray(payload.evolution)
        && Array.isArray(payload.flags);
      if ((url.indexOf("/api/analytics?") === 0 && !validAnalytics)
        || (url === "/api/stations/latest" && !validSnapshot)
        || (url.indexOf("/api/ml/profiles?") === 0 && !validProfiles)) {
        const error = new Error("The service returned an unexpected response shape.");
        error.status = 502;
        throw error;
      }
      return {
        data: payload,
        requestMs: Math.round(performance.now() - requestStartedAt),
        responseFinishedAt: performance.now()
      };
    } catch (error) {
      if (timedOut && generation === state.generation) throw new Error("Request timed out.");
      throw error;
    } finally {
      clearRequestTimer(controller, timeout);
    }
  }

  function showUpdating() {
    state.errorMessage = null;
    state.errorRetained = false;
    const last = state.page === "analytics" ? state.lastAnalyticsAt
      : state.page === "map" ? state.lastSnapshotAt : state.lastProfilesAt;
    const hasData = state.page === "analytics" ? Boolean(state.analytics)
      : state.page === "map" ? Boolean(state.snapshot) : Boolean(state.profiles);
    $("loading").hidden = hasData;
    if (hasData) {
      state.connectionMessage = {
        key: "updating",
        values: { time: last ? Core.formatTimestamp(last) : t("unknown") }
      };
    } else {
      $("loading").querySelector("span:last-child").textContent = t(
        state.page === "map" ? "loadingStation"
          : state.page === "profiles" ? "loadingProfiles" : "initialLoading"
      );
      state.connectionMessage = null;
    }
    renderStatus();
  }

  function errorMessage(error) {
    $("loading").hidden = true;
    if (error.status === 401 || error.status === 403) {
      state.errorMessage = { key: "authError" };
      state.connectionMessage = null;
      state.errorRetained = false;
      renderStatus();
      return;
    }
    if (error.status === 400) {
      state.errorMessage = { key: "requestError", values: { message: error.message } };
      state.connectionMessage = null;
      state.errorRetained = false;
      renderStatus();
      return;
    }
    const seconds = retryDelaySeconds();
    state.errorMessage = { key: "errorLoading", values: { message: error.message } };
    state.connectionMessage = {
      key: error.status ? "serviceError" : "networkError",
      values: { seconds: seconds }
    };
    state.errorRetained = state.page === "analytics" ? Boolean(state.analytics)
      : state.page === "map" ? Boolean(state.snapshot) : Boolean(state.profiles);
    renderStatus();
  }

  function renderStatus() {
    $("error-message").hidden = !state.errorMessage;
    $("error-message").textContent = state.errorMessage
      ? t(state.errorMessage.key, state.errorMessage.values) : "";
    $("connection-status").textContent = state.connectionMessage
      ? t(state.connectionMessage.key, state.connectionMessage.values) : "";
    if (state.errorRetained && state.connectionMessage) {
      $("connection-status").textContent += " " + t("resultsRetained");
    }
  }

  function retryDelaySeconds() {
    return Math.min(60, 5 * Math.pow(2, Math.min(Math.max(0, state.retries - 1), 4)));
  }

  function schedulePoll(delay) {
    clearTimeout(state.timer);
    if (document.hidden) return;
    state.timer = setTimeout(pollNow, delay);
  }

  async function pollNow() {
    clearTimeout(state.timer);
    if (document.hidden) return;
    let url;
    try {
      url = state.page === "analytics" ? paramsForAnalytics()
        : state.page === "map" ? "/api/stations/latest" : paramsForProfiles();
    } catch (_) {
      $("loading").hidden = true;
      state.errorMessage = { key: "invalidFilter" };
      state.connectionMessage = null;
      state.errorRetained = false;
      renderStatus();
      return;
    }
    const generation = state.generation;
    showUpdating();
    try {
      const result = await fetchJson(url, generation);
      if (!result || generation !== state.generation) return;
      const fetchedAt = new Date().toISOString();
      const renderStartedAt = performance.now();
      if (state.page === "analytics") {
        state.analytics = result.data;
        state.lastAnalyticsAt = fetchedAt;
        renderAnalytics();
        $("last-analytics-update").textContent = t("lastAnalytics", { time: Core.formatTimestamp(fetchedAt) });
      } else if (state.page === "map") {
        state.snapshot = result.data;
        state.lastSnapshotAt = fetchedAt;
        renderSnapshot();
      } else {
        state.profiles = result.data;
        state.lastProfilesAt = fetchedAt;
        renderProfiles();
        $("last-profiles-update").textContent = t("lastProfiles", {
          time: Core.formatTimestamp(fetchedAt)
        });
      }
      const renderMs = Math.round(performance.now() - renderStartedAt);
      state.retries = 0;
      $("loading").hidden = true;
      state.errorMessage = null;
      state.errorRetained = false;
      state.connectionMessage = {
        key: "updatedWithTiming",
        values: {
          time: Core.formatTimestamp(fetchedAt),
          requestMs: result.requestMs,
          renderMs: renderMs
        }
      };
      renderStatus();
      const pollInterval = state.page === "profiles" ? 30000 : 5000;
      schedulePoll(Math.max(0, pollInterval - (performance.now() - result.responseFinishedAt)));
    } catch (error) {
      if (generation !== state.generation || error.name === "AbortError") return;
      if (error.status !== 400) state.retries += 1;
      errorMessage(error);
      if (error.status !== 400) {
        schedulePoll(Math.min(60000, 5000 * Math.pow(2, Math.min(state.retries - 1, 4))));
      }
    }
  }

  function statusKind(station) {
    const status = station.status;
    if (!status) return "unknown";
    if (status.num_bikes_available === 0) return "empty";
    if (status.num_docks_available === 0) return "full";
    return "reported";
  }

  function statusLabel(station) {
    return t(statusKind(station));
  }

  function ensureMap() {
    if (state.map || !window.L) return;
    state.map = L.map("station-map", { zoomControl: false });
    state.map.setView([40.7315, -74.045], 13);
    L.control.zoom({
      zoomInTitle: t("zoomIn"),
      zoomOutTitle: t("zoomOut")
    }).addTo(state.map);
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });
    tiles.on("tileerror", function () {
      state.tileError = true;
      $("map-tile-error").hidden = false;
    });
    tiles.addTo(state.map);
  }

  function markerColor(kind) {
    return { unknown: "#596b73", empty: "#c33e37", full: "#d18715", reported: "#087f9d" }[kind];
  }

  function selectStation(stationId) {
    state.selectedStationId = stationId;
    if (state.snapshot) renderSnapshot();
    const marker = state.markerById.get(stationId);
    if (marker && state.map) marker.openPopup();
  }

  function detailItem(label, value) {
    const item = document.createElement("div");
    item.className = "detail-item";
    const name = document.createElement("strong");
    name.textContent = label;
    const content = document.createElement("span");
    content.textContent = value === null || value === undefined ? t("unknown") : String(value);
    item.append(name, content);
    return item;
  }

  function renderDetail(station) {
    const container = $("detail-content");
    container.replaceChildren();
    $("detail-title").textContent = station.name + " (" + station.station_id + ")";
    if (!station.mappable) container.appendChild(detailItem(t("notMappable"), t("unknown")));
    container.append(
      detailItem(t("city"), station.city),
      detailItem(t("capacity"), station.capacity)
    );
    const status = station.status;
    if (!status) {
      container.appendChild(detailItem(t("lastReported"), t("emptyStatus")));
    } else {
      container.append(
        detailItem(t("bikesAvailable"), status.num_bikes_available),
        detailItem(t("ebikesIncluded"), status.num_ebikes_available),
        detailItem(t("docksAvailable"), status.num_docks_available),
        detailItem(t("disabledBikes"), status.num_bikes_disabled),
        detailItem(t("disabledDocks"), status.num_docks_disabled),
        detailItem(t("lastReported"), Core.formatTimestamp(status.reported_at)),
        detailItem(t("sequence"), status.seq),
        detailItem(t("installed"), status.is_installed === 1 ? t("yes") : status.is_installed === 0 ? t("no") : t("unknown")),
        detailItem(t("renting"), status.is_renting === 1 ? t("yes") : status.is_renting === 0 ? t("no") : t("unknown")),
        detailItem(t("returning"), status.is_returning === 1 ? t("yes") : status.is_returning === 0 ? t("no") : t("unknown")),
        detailItem(t("warnings"), status.warnings && status.warnings.length
          ? status.warnings.map(function (warning) { return warning.field + ": " + warning.message; }).join("; ")
          : t("noWarnings"))
      );
    }
    $("station-detail").hidden = false;
  }

  function renderSnapshot() {
    const snapshot = state.snapshot;
    if (!snapshot) return;
    const activeTrips = snapshot.active_trips;
    const activeTripsBody = $("active-trips");
    activeTripsBody.replaceChildren();
    $("active-trips-summary").replaceChildren(
      createCard(t("activeTripsCount"), String(activeTrips.length))
    );
    $("active-trips-empty").hidden = activeTrips.length > 0;
    activeTrips.forEach(function (trip) {
      const bikeType = trip.rideable_type === "electric_bike" ? t("electricBike")
        : trip.rideable_type === "classic_bike" ? t("classicBike") : t("unknown");
      const userType = trip.member_casual === "member" ? t("memberUser")
        : trip.member_casual === "casual" ? t("casualUser") : t("unknown");
      const warnings = trip.warnings && trip.warnings.length
        ? trip.warnings.map(function (warning) {
          return warning.field + ": " + warning.message;
        }).join("; ")
        : t("noWarnings");
      addCells(activeTripsBody, [
        trip.ride_id,
        Core.formatTimestamp(trip.started_at),
        trip.start_station_id || t("unknown"),
        bikeType,
        userType,
        warnings
      ]);
    });
    ensureMap();
    const list = $("station-list");
    list.replaceChildren();
    $("station-empty").hidden = snapshot.stations.length > 0;
    $("station-empty").textContent = t("noStations");
    const bounds = [];
    const mappableIds = new Set(snapshot.stations.filter(function (station) {
      return station.mappable;
    }).map(function (station) { return station.station_id; }));
    snapshot.stations.forEach(function (station) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.setAttribute("aria-current", station.station_id === state.selectedStationId ? "true" : "false");
      const title = document.createElement("strong");
      title.textContent = station.name + " (" + station.station_id + ")";
      const summary = document.createElement("span");
      summary.className = "small";
      summary.textContent = station.mappable ? statusLabel(station) : t("notMappable");
      if (station.status) {
        summary.textContent += " · " + t("lastReported") + ": " + Core.formatTimestamp(station.status.reported_at);
      }
      button.append(title, summary);
      button.addEventListener("click", function () { selectStation(station.station_id); });
      item.appendChild(button);
      list.appendChild(item);

      if (!station.mappable || !state.map) return;
      const point = [station.lat, station.lon];
      bounds.push(point);
      const color = markerColor(statusKind(station));
      let marker = state.markerById.get(station.station_id);
      if (!marker) {
        marker = L.circleMarker(point, {
          radius: 8, color: "#fff", weight: 2, fillColor: color, fillOpacity: .92
        }).addTo(state.map);
        marker.on("click", function () { selectStation(station.station_id); });
        state.markerById.set(station.station_id, marker);
      } else {
        marker.setLatLng(point);
        marker.setStyle({ fillColor: color });
      }
      const bikes = station.status ? station.status.num_bikes_available : t("unknown");
      marker.bindPopup(
        "<strong>" + escapeHtml(station.name) + " (" + escapeHtml(station.station_id) + ")</strong><br>"
        + escapeHtml(statusLabel(station)) + "<br>" + escapeHtml(t("bikesAvailable")) + ": "
        + escapeHtml(String(bikes))
      );
    });
    state.markerById.forEach(function (marker, stationId) {
      if (!mappableIds.has(stationId)) {
        state.map.removeLayer(marker);
        state.markerById.delete(stationId);
      }
    });
    if (state.map && !state.didFitMap && bounds.length) {
      state.map.fitBounds(bounds, { padding: [20, 20], maxZoom: 15 });
      state.didFitMap = true;
    }
    if (state.selectedStationId) {
      const selected = snapshot.stations.find(function (station) { return station.station_id === state.selectedStationId; });
      if (selected) renderDetail(selected);
      else {
        state.selectedStationId = null;
        $("station-detail").hidden = true;
      }
    } else {
      $("station-detail").hidden = true;
    }
    const observed = snapshot.stations.filter(function (station) { return station.status; }).length;
    $("last-map-update").textContent = t("mapSnapshot", {
      fetched: Core.formatTimestamp(snapshot.fetched_at),
      event: Core.formatTimestamp(snapshot.latest_committed_event_at)
    }) + " " + t(observed === 1 ? "oneStationObserved" : "stationsObserved", { count: observed });
    $("map-tile-error").hidden = !state.tileError;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  $("language").addEventListener("change", function (event) {
    state.lang = event.target.value === "pt-PT" ? "pt-PT" : "en";
    saveLanguage();
    applyLanguage();
  });
  function filtersChanged(event) {
    syncEndControls(event.target.id === "start");
    clearTimeout(state.filterTimer);
    clearTimeout(state.timer);
    state.generation += 1;
    if (state.request) state.request.abort();
    try {
      parseFilters();
      state.errorMessage = null;
      state.errorRetained = false;
      renderStatus();
      state.filterTimer = setTimeout(function () {
        if (state.page === "analytics" || state.page === "profiles") pollNow();
      }, 350);
    } catch (_) {
      state.errorMessage = { key: "invalidFilter" };
      state.connectionMessage = null;
      state.errorRetained = false;
      renderStatus();
      $("loading").hidden = true;
    }
  }
  $("filters").addEventListener("input", filtersChanged);
  $("filters").addEventListener("change", filtersChanged);
  function profileFiltersChanged() {
    clearTimeout(state.filterTimer);
    clearTimeout(state.timer);
    state.generation += 1;
    if (state.request) state.request.abort();
    try {
      paramsForProfiles();
      state.errorMessage = null;
      state.errorRetained = false;
      renderStatus();
      state.filterTimer = setTimeout(function () {
        if (state.page === "profiles") pollNow();
      }, 350);
    } catch (_) {
      state.errorMessage = { key: "invalidFilter" };
      state.connectionMessage = null;
      state.errorRetained = false;
      renderStatus();
      $("loading").hidden = true;
    }
  }
  $("profile-filters").addEventListener("input", profileFiltersChanged);
  $("profile-filters").addEventListener("change", profileFiltersChanged);
  document.querySelectorAll("nav a[data-route]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      setPage(link.dataset.route, true);
    });
  });
  window.addEventListener("popstate", function () {
    setPage(location.pathname.endsWith("/map") ? "map"
      : location.pathname.endsWith("/profiles") ? "profiles" : "analytics", false);
  });
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) {
      clearTimeout(state.timer);
      state.generation += 1;
      if (state.request) state.request.abort();
    } else {
      state.generation += 1;
      pollNow();
    }
  });

  $("analytics-page").hidden = state.page !== "analytics";
  $("map-page").hidden = state.page !== "map";
  $("profiles-page").hidden = state.page !== "profiles";
  syncEndControls(true);
  applyLanguage();
  pollNow();
}());
