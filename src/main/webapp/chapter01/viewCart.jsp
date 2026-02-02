<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<%@page import="java.util.ArrayList"%>

<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>viewCart</title>
<link rel="stylesheet" type="text/css" href="../css/fromcss.css" />
</head>
<body>
	<div align="center">
		<h2>장바구니</h2>
		<%
		request.setCharacterEncoding("utf-8");
		
		//세션영역에서 상품 리스트 가져오기
		String prodcutname = request.getParameter("product");

		ArrayList<String> list = (ArrayList<String>) session.getAttribute("list");

		if (list != null && !list.isEmpty()) {
		%>
		<ul>
			<%
			for (String product : list) {
			%>
			<li><%=product%></li>
			<%
			}
			%>
		</ul>
		<p>
			총 상품 수:
			<%=list.size()%></p>
		<%
		} else {
		%>
		<p>장바구니가 비어 있습니다.</p>
		<%
		}
		%>
		<hr />
		<a href="selectProduct.jsp">상품 추가</a>
	</div>
</body>
</html>